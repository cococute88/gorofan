"""Entry Store service tests against isolated temporary SQLite databases."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.errors import NotFound, ValidationAppError
from app.db.base import Base
from app.models.character import Character
from app.models.entry import Entry
from app.models.novel import Work
from app.models.user import User
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
            status=EntryStatus.CANON,
            content="Keeps every promise.",
            provenance=_human_provenance(),
        )
        created = await service.create(session, owner.id, dto)
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
        current = await service.create(
            session, owner.id, _note(status=EntryStatus.CANON, content="The gate is locked.")
        )
        replacement = await service.create(
            session,
            owner.id,
            _note(status=EntryStatus.PROPOSED, content="The gate is open."),
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
