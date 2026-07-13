"""RFC-003 Store-wide retrieval integration tests."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.models.character import Character
from app.models.entry import Entry
from app.models.novel import Work
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
