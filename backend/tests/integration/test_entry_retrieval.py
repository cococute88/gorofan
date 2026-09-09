"""RFC-003 Store-wide retrieval integration tests."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.character import Character
from app.models.chat import ChatSession, Message
from app.models.entry import Entry
from app.models.novel import Chapter, Work
from app.models.user import User
from app.models.world import World
from app.schemas.entry import (
    EntryRetrievalTaskKind,
    EntryRetrieveRequest,
    EntryScope,
    EntryScopeSelector,
    EntryStatus,
    EntrySubjectFilter,
    EntrySubjectType,
    EntryType,
    StorySummaryChronologyAnchor,
    StorySummaryChronologyRequest,
    StorySummaryGenerationOperation,
)
from app.services.entry_service import EntryService


@pytest.fixture()
async def entry_db(tmp_path):
    database = tmp_path / "retrieval.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database.as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        yield sessionmaker
    finally:
        await engine.dispose()


async def _owner(session: AsyncSession, email: str) -> User:
    user = User(email=email, display_name=email)
    session.add(user)
    await session.flush()
    return user


def _entry(
    user_id: str,
    *,
    content: str,
    status: EntryStatus = EntryStatus.CANON,
    scope_kind: EntryScope = EntryScope.USER,
    scope_id: str | None = None,
    entry_type: EntryType = EntryType.NOTE,
    subject_type: EntrySubjectType | None = None,
    subject_id: str | None = None,
    subject_data: dict | None = None,
    priority: int = 50,
) -> Entry:
    return Entry(
        user_id=user_id,
        scope_kind=scope_kind.value,
        scope_id=scope_id,
        subject_type=subject_type.value if subject_type else None,
        subject_id=subject_id,
        subject_data=subject_data or {},
        type=entry_type.value,
        status=status.value,
        content=content,
        data={},
        provenance={
            "source_kind": "user",
            "capture_method": "human-authored",
            "producer": "retrieval-test",
        },
        priority=priority,
        accepted_at=datetime(2026, 1, 1, tzinfo=UTC)
        if status is EntryStatus.CANON
        else None,
    )


def _request(
    user_id: str,
    *scopes: EntryScopeSelector,
    budget: int,
    **updates,
) -> EntryRetrieveRequest:
    return EntryRetrieveRequest(
        user_id=user_id,
        scopes=list(scopes) or [EntryScopeSelector(scope_kind=EntryScope.USER)],
        budget=budget,
        **updates,
    )


def _chronology_request(
    user_id: str,
    work_id: str,
    target: Chapter,
    *,
    legacy_ids: tuple[str, ...] = (),
    budget: int = 4096,
    limit: int = 20,
) -> EntryRetrieveRequest:
    return _request(
        user_id,
        EntryScopeSelector(scope_kind=EntryScope.WORK, scope_id=work_id),
        budget=budget,
        limit=limit,
        task_kind=EntryRetrievalTaskKind.SCENE,
        story_summary_chronology=StorySummaryChronologyRequest(
            anchor=StorySummaryChronologyAnchor(
                owner_id=user_id,
                work_id=work_id,
                chapter_id=target.id,
                chapter_index=target.index,
                operation=StorySummaryGenerationOperation.CONTINUE,
            ),
            substantive_legacy_chapter_ids=legacy_ids,
        ),
    )


def _summary(
    user_id: str,
    work_id: str,
    chapter_id: str | None,
    content: str,
    *,
    subject_type: EntrySubjectType = EntrySubjectType.CHAPTER,
    level: str | None = None,
    created_at_chapter_id: str | None = None,
    priority: int = 50,
) -> Entry:
    entry = _entry(
        user_id,
        content=content,
        scope_kind=EntryScope.WORK,
        scope_id=work_id,
        entry_type=EntryType.STORY_SUMMARY,
        subject_type=subject_type,
        subject_id=chapter_id,
        priority=priority,
    )
    entry.data = {} if level is None else {"level": level}
    entry.created_at_chapter_id = created_at_chapter_id
    return entry


@pytest.mark.asyncio
async def test_owner_and_canon_default_with_explicit_history_status(entry_db) -> None:
    service = EntryService()
    async with entry_db() as session:
        owner = await _owner(session, "retrieve-owner@example.com")
        other = await _owner(session, "retrieve-other@example.com")
        entries = [
            _entry(owner.id, content="owner canon"),
            _entry(owner.id, content="owner rejected", status=EntryStatus.REJECTED),
            _entry(owner.id, content="owner superseded", status=EntryStatus.SUPERSEDED),
            _entry(owner.id, content="owner proposal", status=EntryStatus.PROPOSED),
            _entry(other.id, content="foreign canon"),
        ]
        session.add_all(entries)
        await session.commit()

        result = await service.retrieve(session, _request(owner.id, budget=4096))
        assert [item.entry.content for item in result.items] == ["owner canon"]

        rejected = await service.retrieve(
            session,
            _request(
                owner.id,
                budget=4096,
                status_filters=[EntryStatus.REJECTED],
            ),
        )
        assert [item.entry.content for item in rejected.items] == ["owner rejected"]

        history = await service.retrieve(
            session,
            _request(
                owner.id,
                budget=4096,
                include_rejected=True,
                include_superseded=True,
                limit=10,
            ),
        )
        assert {item.entry.content for item in history.items} == {
            "owner canon",
            "owner rejected",
            "owner superseded",
        }


@pytest.mark.asyncio
async def test_scope_type_subject_and_chat_private_boundaries(entry_db) -> None:
    service = EntryService()
    async with entry_db() as session:
        owner = await _owner(session, "retrieve-scope@example.com")
        first_work = Work(user_id=owner.id, title="First")
        second_work = Work(user_id=owner.id, title="Second")
        first_character = Character(user_id=owner.id, name="First lead")
        second_character = Character(user_id=owner.id, name="Second lead")
        world = World(user_id=owner.id, name="First world")
        session.add_all([first_work, second_work, first_character, second_character, world])
        await session.flush()
        first = _entry(
            owner.id,
            content="first voice",
            scope_kind=EntryScope.WORK,
            scope_id=first_work.id,
            entry_type=EntryType.CHARACTER_VOICE,
            subject_type=EntrySubjectType.CHARACTER,
            subject_id=first_character.id,
        )
        wrong_type = _entry(
            owner.id,
            content="first fact",
            scope_kind=EntryScope.WORK,
            scope_id=first_work.id,
            entry_type=EntryType.STORY_FACT,
        )
        other_scope = _entry(
            owner.id,
            content="second voice",
            scope_kind=EntryScope.WORK,
            scope_id=second_work.id,
            entry_type=EntryType.CHARACTER_VOICE,
            subject_type=EntrySubjectType.CHARACTER,
            subject_id=second_character.id,
        )
        world_scope_entry = _entry(
            owner.id,
            content="world rule",
            scope_kind=EntryScope.WORLD,
            scope_id=world.id,
            entry_type=EntryType.WORLD_FACT,
        )
        session.add_all([first, wrong_type, other_scope, world_scope_entry])
        await session.commit()

        work_scope = EntryScopeSelector(scope_kind=EntryScope.WORK, scope_id=first_work.id)
        result = await service.retrieve(
            session,
            _request(
                owner.id,
                work_scope,
                budget=4096,
                entry_types=[EntryType.CHARACTER_VOICE],
                subject_filters=[
                    EntrySubjectFilter(
                        subject_type=EntrySubjectType.CHARACTER,
                        subject_id=first_character.id,
                    )
                ],
            ),
        )
        assert [item.entry.id for item in result.items] == [first.id]

        private_only = await service.retrieve(
            session,
            _request(
                owner.id,
                EntryScopeSelector(scope_kind=EntryScope.CHAT_PRIVATE),
                budget=4096,
            ),
        )
        assert private_only.items == []

        mixed = await service.retrieve(
            session,
            _request(
                owner.id,
                EntryScopeSelector(scope_kind=EntryScope.CHAT_PRIVATE),
                work_scope,
                budget=4096,
                limit=10,
            ),
        )
        assert {item.entry.id for item in mixed.items} == {first.id, wrong_type.id}

        world_result = await service.retrieve(
            session,
            _request(
                owner.id,
                EntryScopeSelector(scope_kind=EntryScope.WORLD, scope_id=world.id),
                budget=4096,
            ),
        )
        assert [item.entry.id for item in world_result.items] == [world_scope_entry.id]


@pytest.mark.asyncio
async def test_keyword_ranking_and_empty_result(entry_db) -> None:
    service = EntryService()
    async with entry_db() as session:
        owner = await _owner(session, "retrieve-keyword@example.com")
        weak = _entry(owner.id, content="The winter palace is quiet.")
        strong = _entry(owner.id, content="달빛 아래 황궁의 비밀 문이 열린다.")
        session.add_all([weak, strong])
        await session.commit()

        result = await service.retrieve(
            session,
            _request(owner.id, budget=4096, beat="황궁 비밀", limit=10),
        )
        assert [item.entry.id for item in result.items][:2] == [strong.id, weak.id]
        assert result.items[0].matched_terms == ["비밀", "황궁"]

        empty = await service.retrieve(
            session,
            _request(
                owner.id,
                budget=4096,
                entry_types=[EntryType.RELATIONSHIP_STATE],
            ),
        )
        assert empty.items == []
        assert empty.total_estimated_tokens == 0


@pytest.mark.asyncio
async def test_limit_exclusions_are_traced_separately_from_budget(entry_db) -> None:
    service = EntryService()
    async with entry_db() as session:
        owner = await _owner(session, "retrieve-limit@example.com")
        high = _entry(owner.id, content="high", priority=100)
        medium = _entry(owner.id, content="medium", priority=50)
        low = _entry(owner.id, content="low", priority=0)
        session.add_all([high, medium, low])
        await session.commit()

        result = await service.retrieve(
            session,
            _request(owner.id, budget=1000, limit=1),
        )

        assert [item.entry.id for item in result.items] == [high.id]
        assert set(result.trace.limit_rejected_entry_ids) == {medium.id, low.id}
        assert result.trace.budget_rejected_entry_ids == []


@pytest.mark.asyncio
async def test_soft_deleted_and_missing_anchors_are_excluded_before_ranking(entry_db) -> None:
    service = EntryService()
    async with entry_db() as session:
        owner = await _owner(session, "retrieve-anchor@example.com")
        active_work = Work(user_id=owner.id, title="Active")
        deleted_work = Work(
            user_id=owner.id,
            title="Deleted",
            deleted_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
        active_character = Character(user_id=owner.id, name="Active lead")
        deleted_character = Character(
            user_id=owner.id,
            name="Deleted lead",
            deleted_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
        session.add_all([active_work, deleted_work, active_character, deleted_character])
        await session.flush()
        valid = _entry(
            owner.id,
            content="valid",
            scope_kind=EntryScope.WORK,
            scope_id=active_work.id,
            entry_type=EntryType.CHARACTER_IDENTITY,
            subject_type=EntrySubjectType.CHARACTER,
            subject_id=active_character.id,
        )
        deleted_scope = _entry(
            owner.id,
            content="deleted scope",
            scope_kind=EntryScope.WORK,
            scope_id=deleted_work.id,
        )
        missing_scope = _entry(
            owner.id,
            content="missing scope",
            scope_kind=EntryScope.WORK,
            scope_id="missing-work",
        )
        deleted_subject = _entry(
            owner.id,
            content="deleted subject",
            scope_kind=EntryScope.WORK,
            scope_id=active_work.id,
            entry_type=EntryType.CHARACTER_IDENTITY,
            subject_type=EntrySubjectType.CHARACTER,
            subject_id=deleted_character.id,
        )
        missing_subject = _entry(
            owner.id,
            content="missing subject",
            scope_kind=EntryScope.WORK,
            scope_id=active_work.id,
            entry_type=EntryType.CHARACTER_IDENTITY,
            subject_type=EntrySubjectType.CHARACTER,
            subject_id="missing-character",
        )
        session.add_all(
            [valid, deleted_scope, missing_scope, deleted_subject, missing_subject]
        )
        await session.commit()

        result = await service.retrieve(
            session,
            _request(
                owner.id,
                EntryScopeSelector(scope_kind=EntryScope.WORK, scope_id=active_work.id),
                EntryScopeSelector(scope_kind=EntryScope.WORK, scope_id=deleted_work.id),
                EntryScopeSelector(scope_kind=EntryScope.WORK, scope_id="missing-work"),
                budget=4096,
                limit=10,
            ),
        )
        assert [item.entry.id for item in result.items] == [valid.id]
        assert set(result.trace.excluded_orphaned_entry_ids) == {
            deleted_scope.id,
            missing_scope.id,
            deleted_subject.id,
            missing_subject.id,
        }


@pytest.mark.asyncio
async def test_voice_task_exemplar_boost_reaches_service_result(entry_db) -> None:
    service = EntryService()
    async with entry_db() as session:
        owner = await _owner(session, "retrieve-exemplar@example.com")
        character = Character(user_id=owner.id, name="Lead")
        session.add(character)
        await session.flush()
        voice = _entry(
            owner.id,
            content="Polite speech guidance",
            scope_kind=EntryScope.CHARACTER,
            scope_id=character.id,
            entry_type=EntryType.CHARACTER_VOICE,
            subject_type=EntrySubjectType.CHARACTER,
            subject_id=character.id,
        )
        exemplar = _entry(
            owner.id,
            content="A concrete approved line",
            scope_kind=EntryScope.CHARACTER,
            scope_id=character.id,
            entry_type=EntryType.CHARACTER_EXEMPLAR,
            subject_type=EntrySubjectType.CHARACTER,
            subject_id=character.id,
        )
        session.add_all([voice, exemplar])
        await session.commit()

        result = await service.retrieve(
            session,
            _request(
                owner.id,
                EntryScopeSelector(scope_kind=EntryScope.CHARACTER, scope_id=character.id),
                budget=4096,
                task_kind=EntryRetrievalTaskKind.VOICE,
            ),
        )
        assert [item.entry.id for item in result.items][:2] == [exemplar.id, voice.id]
        assert result.items[0].score_breakdown.exemplar == 1.0


@pytest.mark.asyncio
async def test_novel_chronology_excludes_non_prior_before_ranking(entry_db) -> None:
    service = EntryService()
    async with entry_db() as session:
        owner = await _owner(session, "chronology-owner@example.com")
        foreign = await _owner(session, "chronology-foreign@example.com")
        work = Work(user_id=owner.id, title="Main")
        other_work = Work(user_id=owner.id, title="Other")
        foreign_work = Work(user_id=foreign.id, title="Foreign")
        session.add_all([work, other_work, foreign_work])
        await session.flush()
        chapter_1 = Chapter(work_id=work.id, user_id=owner.id, index=1, title="1")
        chapter_2 = Chapter(work_id=work.id, user_id=owner.id, index=2, title="2")
        target = Chapter(work_id=work.id, user_id=owner.id, index=3, title="3")
        chapter_4 = Chapter(work_id=work.id, user_id=owner.id, index=4, title="4")
        chapter_5 = Chapter(work_id=work.id, user_id=owner.id, index=5, title="5")
        chapter_7 = Chapter(work_id=work.id, user_id=owner.id, index=7, title="7")
        cross_work = Chapter(
            work_id=other_work.id, user_id=owner.id, index=876543, title="Other 1"
        )
        foreign_chapter = Chapter(
            work_id=foreign_work.id,
            user_id=foreign.id,
            index=987654,
            title="Foreign 1",
        )
        session.add_all(
            [
                chapter_1,
                chapter_2,
                target,
                chapter_4,
                chapter_5,
                chapter_7,
                cross_work,
                foreign_chapter,
            ]
        )
        await session.flush()
        summaries = [
            _summary(
                owner.id,
                work.id,
                chapter_1.id,
                "chapter one",
                created_at_chapter_id=chapter_2.id,
            ),
            _summary(owner.id, work.id, chapter_2.id, "chapter two"),
            _summary(owner.id, work.id, target.id, "current"),
            _summary(owner.id, work.id, chapter_7.id, "future", priority=100),
            _summary(
                owner.id,
                work.id,
                work.id,
                "work-level unknown",
                subject_type=EntrySubjectType.WORK,
            ),
            _summary(owner.id, work.id, chapter_1.id, "arc unknown", level="arc"),
            _summary(owner.id, work.id, cross_work.id, "cross work"),
            _summary(owner.id, work.id, foreign_chapter.id, "foreign"),
            _summary(owner.id, work.id, "missing-chapter", "orphan"),
        ]
        session.add_all(summaries)
        await session.commit()

        statements: list[str] = []

        def _capture_sql(_conn, _cursor, statement, _parameters, _context, _many):  # noqa: ANN001
            statements.append(statement)

        engine = entry_db.kw["bind"]
        event.listen(engine.sync_engine, "before_cursor_execute", _capture_sql)
        try:
            result = await service.retrieve(
                session, _chronology_request(owner.id, work.id, target)
            )
            rerun = await service.retrieve(
                session, _chronology_request(owner.id, work.id, target)
            )
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", _capture_sql)

        assert result.model_dump() == rerun.model_dump()
        assert [item.entry.content for item in result.items] == [
            "chapter one",
            "chapter two",
        ]
        assert [
            item.story_summary_chronology.source_chapter_index
            for item in result.items
            if item.story_summary_chronology is not None
        ] == [1, 2]
        exclusions = {
            exclusion.reason
            for exclusion in result.trace.story_summary_chronology_exclusions
        }
        assert {
            "current_chapter_summary",
            "future_chapter_summary",
            "missing_chapter_subject",
            "unsupported_summary_level",
            "cross_work_source_chapter",
            "foreign_source_chapter",
            "orphan_source_chapter",
        } <= exclusions
        boundary_exclusions = {
            exclusion.reason: exclusion
            for exclusion in result.trace.story_summary_chronology_exclusions
            if exclusion.reason
            in {"foreign_source_chapter", "cross_work_source_chapter"}
        }
        assert boundary_exclusions["foreign_source_chapter"].source_chapter_index is None
        assert boundary_exclusions["cross_work_source_chapter"].source_chapter_index is None
        assert "987654" not in str(result.model_dump())
        assert "876543" not in str(result.model_dump())
        index_queries = [
            statement.lower()
            for statement in statements
            if 'chapters."index"' in statement.lower()
        ]
        assert index_queries
        assert all(
            "chapters.work_id = ?" in statement
            and "chapters.user_id = ?" in statement
            and "works.user_id = ?" in statement
            for statement in index_queries
        )
        assert result.total_estimated_tokens == sum(
            item.estimated_tokens for item in result.items
        )


@pytest.mark.asyncio
async def test_required_provenance_anchors_are_revalidated_before_ranking(entry_db) -> None:
    service = EntryService()
    async with entry_db() as session:
        owner = await _owner(session, "required-provenance@example.com")
        foreign = await _owner(session, "required-provenance-foreign@example.com")
        work = Work(user_id=owner.id, title="Required provenance")
        character = Character(user_id=owner.id, name="Bookmark character")
        session.add_all([work, character])
        await session.flush()

        subjects = [
            Chapter(work_id=work.id, user_id=owner.id, index=index)
            for index in range(1, 5)
        ]
        chapter_anchor = Chapter(work_id=work.id, user_id=owner.id, index=10)
        edit_diff_anchor = Chapter(work_id=work.id, user_id=owner.id, index=11)
        target = Chapter(work_id=work.id, user_id=owner.id, index=20)
        chat = ChatSession(user_id=owner.id, character_id=character.id)
        session.add_all([*subjects, chapter_anchor, edit_diff_anchor, target, chat])
        await session.flush()
        bookmark = Message(
            chat_session_id=chat.id,
            user_id=owner.id,
            role="user",
            content="bookmark source",
        )
        session.add(bookmark)
        await session.flush()

        normal = _summary(owner.id, work.id, subjects[0].id, "normal prior", priority=1)
        session.add(normal)
        await session.commit()
        request = _chronology_request(owner.id, work.id, target, budget=64, limit=1)
        baseline = await service.retrieve(session, request)

        required_sources = (
            ("chapter", chapter_anchor.id),
            ("edit-diff", edit_diff_anchor.id),
            ("chat-bookmark", bookmark.id),
        )
        broken_entries: list[Entry] = []
        for subject, (source_kind, source_id) in zip(
            subjects[1:], required_sources, strict=True
        ):
            entry = _summary(
                owner.id,
                work.id,
                subject.id,
                f"{source_kind} blocker " * 200,
                priority=100,
            )
            entry.status = EntryStatus.PROPOSED.value
            entry.accepted_at = None
            entry.provenance = {
                "source_kind": source_kind,
                "source_id": source_id,
                "capture_method": "ai-extracted",
                "producer": "required-provenance-test",
            }
            session.add(entry)
            await session.commit()
            await service.accept_review_entry(session, owner.id, entry.id)
            broken_entries.append(entry)

        # All three anchors were live and owner-valid at acceptance. Break them
        # independently afterward: hard-delete, foreign ownership, hard-delete.
        await session.delete(chapter_anchor)
        edit_diff_anchor.user_id = foreign.id
        await session.delete(bookmark)
        await session.commit()

        result = await service.retrieve(session, request)

        assert [item.entry.id for item in baseline.items] == [normal.id]
        assert [item.entry.id for item in result.items] == [normal.id]
        assert result.items[0].score == baseline.items[0].score
        assert result.total_estimated_tokens == baseline.total_estimated_tokens
        broken_ids = {entry.id for entry in broken_entries}
        provenance_exclusions = {
            exclusion.entry_id: exclusion
            for exclusion in result.trace.story_summary_chronology_exclusions
            if exclusion.reason == "invalid_required_provenance_anchor"
        }
        assert set(provenance_exclusions) == broken_ids
        assert all(
            exclusion.source_chapter_index is None
            for exclusion in provenance_exclusions.values()
        )
        assert broken_ids.isdisjoint(result.trace.budget_rejected_entry_ids)
        assert broken_ids.isdisjoint(result.trace.limit_rejected_entry_ids)


@pytest.mark.asyncio
@pytest.mark.parametrize("source_kind", ["user", "import", "reference"])
@pytest.mark.parametrize("with_different_origin", [False, True])
async def test_generic_provenance_and_optional_origin_remain_eligible(
    entry_db, source_kind: str, with_different_origin: bool
) -> None:
    service = EntryService()
    async with entry_db() as session:
        owner = await _owner(
            session, f"generic-{source_kind}-{with_different_origin}@example.com"
        )
        work = Work(user_id=owner.id, title="Generic provenance")
        session.add(work)
        await session.flush()
        subject = Chapter(work_id=work.id, user_id=owner.id, index=1)
        different_origin = Chapter(work_id=work.id, user_id=owner.id, index=2)
        target = Chapter(work_id=work.id, user_id=owner.id, index=3)
        session.add_all([subject, different_origin, target])
        await session.flush()
        entry = _summary(
            owner.id,
            work.id,
            subject.id,
            f"eligible {source_kind}",
            created_at_chapter_id=(different_origin.id if with_different_origin else None),
        )
        entry.provenance = {
            "source_kind": source_kind,
            "source_id": owner.id if source_kind == "user" else "external-locator",
            "capture_method": (
                "imported" if source_kind == "import" else "human-authored"
            ),
            "producer": "generic-provenance-test",
        }
        session.add(entry)
        await session.commit()

        result = await service.retrieve(
            session, _chronology_request(owner.id, work.id, target)
        )

        assert [item.entry.id for item in result.items] == [entry.id]
        assert result.trace.excluded_orphaned_entry_ids == []
        assert result.trace.story_summary_chronology_exclusions == []


@pytest.mark.asyncio
async def test_ineligible_summary_addition_cannot_change_prior_selection(entry_db) -> None:
    service = EntryService()
    async with entry_db() as session:
        owner = await _owner(session, "chronology-property@example.com")
        work = Work(user_id=owner.id, title="Property")
        session.add(work)
        await session.flush()
        prior = Chapter(work_id=work.id, user_id=owner.id, index=1)
        target = Chapter(work_id=work.id, user_id=owner.id, index=2)
        future = Chapter(work_id=work.id, user_id=owner.id, index=7)
        session.add_all([prior, target, future])
        await session.flush()
        prior_entry = _summary(owner.id, work.id, prior.id, "stable prior", priority=1)
        session.add(prior_entry)
        await session.commit()

        request = _chronology_request(owner.id, work.id, target, limit=1)
        before = await service.retrieve(session, request)
        future_entry = _summary(
            owner.id, work.id, future.id, "future " * 200, priority=100
        )
        unknown_entry = _summary(
            owner.id,
            work.id,
            work.id,
            "unknown " * 200,
            subject_type=EntrySubjectType.WORK,
            priority=100,
        )
        session.add_all([future_entry, unknown_entry])
        await session.commit()

        after = await service.retrieve(session, request)

        assert [item.entry.id for item in before.items] == [prior_entry.id]
        assert [item.entry.id for item in after.items] == [prior_entry.id]
        assert before.items[0].score == after.items[0].score
        assert before.total_estimated_tokens == after.total_estimated_tokens
        assert after.trace.limit_rejected_entry_ids == []
        assert after.trace.budget_rejected_entry_ids == []


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_summary", ["", "   ", "\n\n", "actual legacy"])
async def test_legacy_overlap_uses_substantive_identity_predicate(
    entry_db, legacy_summary: str
) -> None:
    service = EntryService()
    async with entry_db() as session:
        owner = await _owner(session, f"legacy-{repr(legacy_summary)}@example.com")
        work = Work(user_id=owner.id, title="Legacy")
        session.add(work)
        await session.flush()
        prior = Chapter(
            work_id=work.id,
            user_id=owner.id,
            index=1,
            summary=legacy_summary,
        )
        target = Chapter(work_id=work.id, user_id=owner.id, index=2)
        session.add_all([prior, target])
        await session.flush()
        entry = _summary(owner.id, work.id, prior.id, "entry fallback")
        session.add(entry)
        await session.commit()

        legacy_ids = (prior.id,) if legacy_summary.strip() else ()
        result = await service.retrieve(
            session,
            _chronology_request(owner.id, work.id, target, legacy_ids=legacy_ids),
        )

        if legacy_summary.strip():
            assert result.items == []
            assert result.trace.story_summary_chronology_exclusions[0].reason == (
                "legacy_summary_authority_overlap"
            )
        else:
            assert [item.entry.id for item in result.items] == [entry.id]


@pytest.mark.asyncio
async def test_duplicate_active_canon_summary_group_is_wholly_excluded(entry_db) -> None:
    service = EntryService()
    async with entry_db() as session:
        owner = await _owner(session, "duplicate-summary@example.com")
        work = Work(user_id=owner.id, title="Duplicate")
        session.add(work)
        await session.flush()
        prior = Chapter(work_id=work.id, user_id=owner.id, index=1)
        target = Chapter(work_id=work.id, user_id=owner.id, index=2)
        session.add_all([prior, target])
        await session.flush()
        first = _summary(owner.id, work.id, prior.id, "first", priority=100)
        second = _summary(owner.id, work.id, prior.id, "second", priority=1)
        session.add_all([first, second])
        await session.commit()

        result = await service.retrieve(
            session, _chronology_request(owner.id, work.id, target)
        )

        assert result.items == []
        assert {
            exclusion.entry_id: exclusion.reason
            for exclusion in result.trace.story_summary_chronology_exclusions
        } == {
            first.id: "duplicate_active_chapter_summary",
            second.id: "duplicate_active_chapter_summary",
        }
