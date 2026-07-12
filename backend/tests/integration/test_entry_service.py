"""Entry Store service tests against isolated temporary SQLite databases."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.errors import NotFound, ValidationAppError
from app.db.base import Base
from app.models.character import Character
from app.models.entry import Entry
from app.models.novel import Chapter, Work
from app.models.user import User
from app.models.world import World
from app.schemas.entry import (
    EntryCreate,
    EntryProvenance,
    EntryScope,
    EntryStatus,
    EntrySubjectType,
    EntryType,
    ProvenanceCaptureMethod,
    ProvenanceSourceKind,
)
from app.services.entry_service import EntryService


@pytest.fixture()
async def entry_db(tmp_path):
    database = tmp_path / "entries.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database.as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        yield sessionmaker
    finally:
        await engine.dispose()


async def _seed_owner(session: AsyncSession, email: str) -> User:
    user = User(email=email, display_name=email)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def _human_provenance() -> EntryProvenance:
    return EntryProvenance(
        source_kind=ProvenanceSourceKind.USER,
        capture_method=ProvenanceCaptureMethod.HUMAN_AUTHORED,
        producer="integration-test",
    )


def _note(*, status: EntryStatus = EntryStatus.CAPTURED, content: str = "fact") -> EntryCreate:
    return EntryCreate(
        scope_kind=EntryScope.USER,
        type=EntryType.NOTE,
        status=status,
        content=content,
        provenance=_human_provenance(),
    )


async def _create_canon_note(
    service: EntryService, session: AsyncSession, user_id: str, content: str
) -> Entry:
    entry = await service.create(session, user_id, _note(content=content))
    entry = await service.update_status(session, user_id, entry.id, EntryStatus.PROPOSED)
    return await service.update_status(session, user_id, entry.id, EntryStatus.CANON)


def _relationship_state(
    work_id: str,
    first_character_id: str,
    second_character_id: str,
    *,
    content: str,
) -> EntryCreate:
    return EntryCreate(
        scope_kind=EntryScope.WORK,
        scope_id=work_id,
        subject_type=EntrySubjectType.CHARACTER_PAIR,
        subject_data={"character_ids": [first_character_id, second_character_id]},
        type=EntryType.RELATIONSHIP_STATE,
        status=EntryStatus.PROPOSED,
        content=content,
        provenance=_human_provenance(),
    )


def _story_summary(work_id: str, chapter_id: str, *, content: str) -> EntryCreate:
    return EntryCreate(
        scope_kind=EntryScope.WORK,
        scope_id=work_id,
        subject_type=EntrySubjectType.CHAPTER,
        subject_id=chapter_id,
        type=EntryType.STORY_SUMMARY,
        status=EntryStatus.PROPOSED,
        content=content,
        provenance=_human_provenance(),
    )


@pytest.mark.asyncio
async def test_owner_boundary_and_status_transitions(entry_db) -> None:
    service = EntryService()
    async with entry_db() as session:
        owner = await _seed_owner(session, "owner@example.com")
        other = await _seed_owner(session, "other@example.com")
        entry = await service.create(session, owner.id, _note())

        assert await service.get(session, owner.id, entry.id) == entry
        with pytest.raises(NotFound):
            await service.get(session, other.id, entry.id)
        with pytest.raises(NotFound):
            await service.update_status(session, other.id, entry.id, EntryStatus.PROPOSED)

        bypassed_canon = _note().model_copy(update={"status": EntryStatus.CANON})
        with pytest.raises(ValidationAppError, match="directly as canon"):
            await service.create(session, owner.id, bypassed_canon)

        entry = await service.update_status(session, owner.id, entry.id, EntryStatus.PROPOSED)
        assert entry.status == EntryStatus.PROPOSED.value
        entry = await service.update_status(session, owner.id, entry.id, EntryStatus.CANON)
        assert entry.status == EntryStatus.CANON.value
        assert entry.accepted_at is not None
        with pytest.raises(ValidationAppError, match="Invalid Entry status transition"):
            await service.update_status(session, owner.id, entry.id, EntryStatus.REJECTED)

        captured_rejection = await service.create(
            session, owner.id, _note(content="Reject captured")
        )
        captured_rejection = await service.update_status(
            session, owner.id, captured_rejection.id, EntryStatus.REJECTED
        )
        assert captured_rejection.rejected_at is not None

        proposed_rejection = await service.create(
            session,
            owner.id,
            _note(status=EntryStatus.PROPOSED, content="Reject proposal"),
        )
        proposed_rejection = await service.update_status(
            session, owner.id, proposed_rejection.id, EntryStatus.REJECTED
        )
        assert proposed_rejection.rejected_at is not None


@pytest.mark.asyncio
async def test_list_filters_and_owned_aggregate_references(entry_db) -> None:
    service = EntryService()
    async with entry_db() as session:
        owner = await _seed_owner(session, "scope-owner@example.com")
        other = await _seed_owner(session, "scope-other@example.com")
        work = Work(user_id=owner.id, title="Owned work")
        character = Character(user_id=owner.id, name="Owned character")
        foreign_work = Work(user_id=other.id, title="Foreign work")
        session.add_all([work, character, foreign_work])
        await session.commit()

        dto = EntryCreate(
            scope_kind=EntryScope.WORK,
            scope_id=work.id,
            subject_type=EntrySubjectType.CHARACTER,
            subject_id=character.id,
            type=EntryType.CHARACTER_IDENTITY,
            content="Keeps every promise.",
            provenance=_human_provenance(),
        )
        created = await service.create(session, owner.id, dto)
        created = await service.update_status(
            session, owner.id, created.id, EntryStatus.PROPOSED
        )
        created = await service.update_status(session, owner.id, created.id, EntryStatus.CANON)
        listed = await service.list(
            session,
            owner.id,
            scope_kind=EntryScope.WORK,
            scope_id=work.id,
            status=EntryStatus.CANON,
            entry_type=EntryType.CHARACTER_IDENTITY,
        )
        assert [item.id for item in listed] == [created.id]
        assert await service.list(session, other.id) == []

        invalid = dto.model_copy(update={"scope_id": foreign_work.id})
        with pytest.raises(ValidationAppError, match="owned active record"):
            await service.create(session, owner.id, invalid)


@pytest.mark.asyncio
async def test_supersession_is_atomic_owner_scoped_and_traceable(entry_db) -> None:
    service = EntryService()
    async with entry_db() as session:
        owner = await _seed_owner(session, "supersede@example.com")
        other = await _seed_owner(session, "supersede-other@example.com")
        current = await _create_canon_note(
            service, session, owner.id, "The gate is locked."
        )
        replacement = await service.create(
            session,
            owner.id,
            _note(status=EntryStatus.PROPOSED, content="The gate is open."),
        )
        foreign_replacement = await service.create(
            session,
            other.id,
            _note(status=EntryStatus.PROPOSED, content="Foreign replacement"),
        )

        with pytest.raises(NotFound):
            await service.supersede(
                session, owner.id, current.id, foreign_replacement.id
            )

        old, new = await service.supersede(session, owner.id, current.id, replacement.id)
        assert old.status == EntryStatus.SUPERSEDED.value
        assert old.superseded_by_entry_id == new.id
        assert old.superseded_at is not None
        assert new.status == EntryStatus.CANON.value
        assert new.accepted_at is not None

        persisted_old = await session.get(Entry, old.id)
        assert persisted_old is not None
        assert persisted_old.superseded_by_entry_id == new.id


@pytest.mark.asyncio
async def test_relationship_state_duplicate_canon_requires_supersede(entry_db) -> None:
    service = EntryService()
    async with entry_db() as session:
        owner = await _seed_owner(session, "relationship-canon@example.com")
        work = Work(user_id=owner.id, title="Relationship work")
        first = Character(user_id=owner.id, name="First")
        second = Character(user_id=owner.id, name="Second")
        session.add_all([work, first, second])
        await session.commit()

        current = await service.create(
            session,
            owner.id,
            _relationship_state(
                work.id, first.id, second.id, content="They distrust each other."
            ),
        )
        current = await service.update_status(
            session, owner.id, current.id, EntryStatus.CANON
        )
        replacement = await service.create(
            session,
            owner.id,
            _relationship_state(
                work.id, second.id, first.id, content="They now trust each other."
            ),
        )

        with pytest.raises(ValidationAppError, match=r"use supersede\(\)"):
            await service.update_status(
                session, owner.id, replacement.id, EntryStatus.CANON
            )
        assert replacement.status == EntryStatus.PROPOSED.value

        old, new = await service.supersede(session, owner.id, current.id, replacement.id)
        assert old.status == EntryStatus.SUPERSEDED.value
        assert new.status == EntryStatus.CANON.value
        assert old.superseded_by_entry_id == new.id


@pytest.mark.asyncio
async def test_story_summary_duplicate_canon_is_rejected(entry_db) -> None:
    service = EntryService()
    async with entry_db() as session:
        owner = await _seed_owner(session, "summary-canon@example.com")
        work = Work(user_id=owner.id, title="Summary work")
        session.add(work)
        await session.flush()
        chapter = Chapter(work_id=work.id, user_id=owner.id, index=1)
        session.add(chapter)
        await session.commit()

        current = await service.create(
            session, owner.id, _story_summary(work.id, chapter.id, content="First summary")
        )
        await service.update_status(session, owner.id, current.id, EntryStatus.CANON)
        duplicate = await service.create(
            session, owner.id, _story_summary(work.id, chapter.id, content="Second summary")
        )

        with pytest.raises(ValidationAppError, match=r"use supersede\(\)"):
            await service.update_status(
                session, owner.id, duplicate.id, EntryStatus.CANON
            )


@pytest.mark.asyncio
async def test_non_single_current_type_still_allows_multiple_canon(entry_db) -> None:
    service = EntryService()
    async with entry_db() as session:
        owner = await _seed_owner(session, "multi-canon@example.com")
        first = await service.create(
            session, owner.id, _note(status=EntryStatus.PROPOSED, content="First note")
        )
        second = await service.create(
            session, owner.id, _note(status=EntryStatus.PROPOSED, content="Second note")
        )

        first = await service.update_status(session, owner.id, first.id, EntryStatus.CANON)
        second = await service.update_status(session, owner.id, second.id, EntryStatus.CANON)

        assert first.status == EntryStatus.CANON.value
        assert second.status == EntryStatus.CANON.value


@pytest.mark.asyncio
async def test_single_current_canon_check_is_owner_scoped(entry_db) -> None:
    service = EntryService()
    async with entry_db() as session:
        first_owner = await _seed_owner(session, "first-canon-owner@example.com")
        second_owner = await _seed_owner(session, "second-canon-owner@example.com")
        shared_identity = {
            "scope_kind": EntryScope.WORK.value,
            "scope_id": "shared-work-id",
            "subject_type": EntrySubjectType.WORK.value,
            "subject_id": "shared-work-id",
            "subject_data": {},
            "type": EntryType.STORY_SUMMARY.value,
            "status": EntryStatus.PROPOSED.value,
            "content": "Owner-specific summary",
            "data": {},
            "provenance": _human_provenance().model_dump(mode="json"),
        }
        first = Entry(user_id=first_owner.id, **shared_identity)
        second = Entry(user_id=second_owner.id, **shared_identity)
        session.add_all([first, second])
        await session.commit()

        first = await service.update_status(
            session, first_owner.id, first.id, EntryStatus.CANON
        )
        second = await service.update_status(
            session, second_owner.id, second.id, EntryStatus.CANON
        )

        assert first.status == EntryStatus.CANON.value
        assert second.status == EntryStatus.CANON.value


@pytest.mark.asyncio
async def test_rejected_and_superseded_entries_do_not_block_canon(entry_db) -> None:
    service = EntryService()
    async with entry_db() as session:
        owner = await _seed_owner(session, "terminal-canon@example.com")
        work = Work(user_id=owner.id, title="Terminal history work")
        session.add(work)
        await session.flush()
        rejected_chapter = Chapter(work_id=work.id, user_id=owner.id, index=1)
        superseded_chapter = Chapter(work_id=work.id, user_id=owner.id, index=2)
        session.add_all([rejected_chapter, superseded_chapter])
        await session.commit()

        rejected = await service.create(
            session,
            owner.id,
            _story_summary(work.id, rejected_chapter.id, content="Rejected summary"),
        )
        await service.update_status(session, owner.id, rejected.id, EntryStatus.REJECTED)
        after_rejected = await service.create(
            session,
            owner.id,
            _story_summary(work.id, rejected_chapter.id, content="Accepted after rejection"),
        )
        after_rejected = await service.update_status(
            session, owner.id, after_rejected.id, EntryStatus.CANON
        )

        superseded = Entry(
            user_id=owner.id,
            scope_kind=EntryScope.WORK.value,
            scope_id=work.id,
            subject_type=EntrySubjectType.CHAPTER.value,
            subject_id=superseded_chapter.id,
            subject_data={},
            type=EntryType.STORY_SUMMARY.value,
            status=EntryStatus.SUPERSEDED.value,
            content="Historical superseded summary",
            data={},
            provenance=_human_provenance().model_dump(mode="json"),
        )
        candidate = Entry(
            user_id=owner.id,
            scope_kind=EntryScope.WORK.value,
            scope_id=work.id,
            subject_type=EntrySubjectType.CHAPTER.value,
            subject_id=superseded_chapter.id,
            subject_data={},
            type=EntryType.STORY_SUMMARY.value,
            status=EntryStatus.PROPOSED.value,
            content="Accepted after supersession history",
            data={},
            provenance=_human_provenance().model_dump(mode="json"),
        )
        session.add_all([superseded, candidate])
        await session.commit()
        candidate = await service.update_status(
            session, owner.id, candidate.id, EntryStatus.CANON
        )

        assert after_rejected.status == EntryStatus.CANON.value
        assert candidate.status == EntryStatus.CANON.value


@pytest.mark.asyncio
async def test_subject_collection_and_provenance_ownership_boundaries(entry_db) -> None:
    service = EntryService()
    async with entry_db() as session:
        owner = await _seed_owner(session, "subject-owner@example.com")
        other = await _seed_owner(session, "subject-other@example.com")
        work = Work(user_id=owner.id, title="Owned work")
        world = World(user_id=owner.id, name="Owned world")
        first = Character(user_id=owner.id, name="First")
        second = Character(user_id=owner.id, name="Second")
        foreign = Character(user_id=other.id, name="Foreign")
        foreign_work = Work(user_id=other.id, title="Foreign work")
        session.add_all([work, world, first, second, foreign, foreign_work])
        await session.flush()
        chapter = Chapter(work_id=work.id, user_id=owner.id, index=1)
        foreign_chapter = Chapter(work_id=foreign_work.id, user_id=other.id, index=1)
        session.add_all([chapter, foreign_chapter])
        await session.commit()

        summary = await service.create(
            session,
            owner.id,
            EntryCreate(
                scope_kind=EntryScope.WORK,
                scope_id=work.id,
                subject_type=EntrySubjectType.CHAPTER,
                subject_id=chapter.id,
                type=EntryType.STORY_SUMMARY,
                content="Chapter summary",
                provenance=_human_provenance(),
            ),
        )
        assert summary.subject_id == chapter.id

        work_fact = await service.create(
            session,
            owner.id,
            EntryCreate(
                scope_kind=EntryScope.WORK,
                scope_id=work.id,
                subject_type=EntrySubjectType.WORK,
                subject_id=work.id,
                type=EntryType.STORY_FACT,
                content="The work begins in winter.",
                provenance=_human_provenance(),
            ),
        )
        assert work_fact.subject_id == work.id

        world_fact = await service.create(
            session,
            owner.id,
            EntryCreate(
                scope_kind=EntryScope.WORLD,
                scope_id=world.id,
                type=EntryType.WORLD_FACT,
                content="Magic has a cost.",
                provenance=_human_provenance(),
            ),
        )
        assert world_fact.scope_id == world.id

        relationship = await service.create(
            session,
            owner.id,
            EntryCreate(
                scope_kind=EntryScope.WORK,
                scope_id=work.id,
                subject_type=EntrySubjectType.CHARACTER_PAIR,
                subject_data={"character_ids": [second.id, first.id]},
                type=EntryType.RELATIONSHIP_STATE,
                content="They distrust each other.",
                provenance=_human_provenance(),
            ),
        )
        expected_pair = sorted([first.id, second.id])
        assert relationship.subject_data["character_ids"] == expected_pair
        assert relationship.subject_id == "|".join(expected_pair)

        with pytest.raises(ValidationAppError, match="owned active record"):
            await service.create(
                session,
                owner.id,
                EntryCreate(
                    scope_kind=EntryScope.WORK,
                    scope_id=work.id,
                    subject_type=EntrySubjectType.CHARACTER_PAIR,
                    subject_data={"character_ids": [first.id, foreign.id]},
                    type=EntryType.RELATIONSHIP_STATE,
                    content="Cross-owner pair",
                    provenance=_human_provenance(),
                ),
            )

        with pytest.raises(ValidationAppError, match="collection scope is unavailable"):
            await service.create(
                session,
                owner.id,
                EntryCreate(
                    scope_kind=EntryScope.COLLECTION,
                    scope_id="collection-id",
                    type=EntryType.STYLE_PREFERENCE,
                    content="Collection style",
                    provenance=_human_provenance(),
                ),
            )

        with pytest.raises(ValidationAppError, match="owned active record"):
            await service.create(
                session,
                owner.id,
                EntryCreate(
                    scope_kind=EntryScope.USER,
                    type=EntryType.NOTE,
                    content="Foreign provenance",
                    provenance=EntryProvenance(
                        source_kind=ProvenanceSourceKind.CHAPTER,
                        source_id=foreign_chapter.id,
                        capture_method=ProvenanceCaptureMethod.HUMAN_AUTHORED,
                        producer="integration-test",
                    ),
                ),
            )
