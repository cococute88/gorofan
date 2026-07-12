"""Minimal owner-safe Entry Store write/read boundary (RFC-002).

This service intentionally does not implement Store-wide retrieval or a Review
Card API. It only establishes validated persistence, lifecycle transitions, and
atomic supersession for later consumers.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound, ValidationAppError
from app.db.base import utcnow
from app.models.character import Character
from app.models.chat import Message
from app.models.entry import Entry
from app.models.novel import Chapter, Work
from app.models.user import User
from app.models.world import World
from app.repositories.entry_repository import EntryRepository
from app.schemas.entry import (
    EntryCreate,
    EntryScope,
    EntryStatus,
    EntrySubjectType,
    EntryType,
    ProvenanceCaptureMethod,
    ProvenanceSourceKind,
)

ALLOWED_STATUS_TRANSITIONS: dict[EntryStatus, set[EntryStatus]] = {
    EntryStatus.CAPTURED: {EntryStatus.PROPOSED, EntryStatus.REJECTED},
    EntryStatus.PROPOSED: {EntryStatus.CANON, EntryStatus.REJECTED},
    EntryStatus.CANON: set(),  # canon -> superseded is atomic through supersede()
    EntryStatus.REJECTED: set(),
    EntryStatus.SUPERSEDED: set(),
}

SINGLE_CURRENT_ENTRY_TYPES: frozenset[EntryType] = frozenset(
    {
        EntryType.RELATIONSHIP_STATE,
        EntryType.STORY_SUMMARY,
    }
)


class EntryService:
    def __init__(self) -> None:
        self.repo = EntryRepository()

    async def create(self, session: AsyncSession, user_id: str, dto: EntryCreate) -> Entry:
        await self._assert_active_owner(session, user_id)
        self._validate_creation_state(dto)
        await self._validate_scope(session, user_id, dto.scope_kind, dto.scope_id)
        subject_id, subject_data = await self._validate_and_normalize_subject(
            session,
            user_id,
            dto.scope_kind,
            dto.scope_id,
            dto.subject_type,
            dto.subject_id,
            dto.subject_data,
        )
        await self._validate_provenance(session, user_id, dto)
        await self._validate_chapter_origin(
            session, user_id, dto.scope_kind, dto.scope_id, dto.created_at_chapter_id
        )

        values = dto.model_dump(mode="json")
        values["subject_id"] = subject_id
        values["subject_data"] = subject_data
        entry = Entry(user_id=user_id, **values)
        await self.repo.add(session, entry)
        await session.commit()
        await session.refresh(entry)
        return entry

    async def get(self, session: AsyncSession, user_id: str, entry_id: str) -> Entry:
        entry = await self.repo.get(session, entry_id, user_id=user_id)
        if entry is None:
            raise NotFound("Entry not found", {"id": entry_id})
        return entry

    async def list(
        self,
        session: AsyncSession,
        user_id: str,
        *,
        scope_kind: EntryScope | None = None,
        scope_id: str | None = None,
        status: EntryStatus | None = None,
        entry_type: EntryType | None = None,
    ) -> list[Entry]:
        return await self.repo.list(
            session,
            user_id=user_id,
            scope_kind=scope_kind.value if scope_kind else None,
            scope_id=scope_id,
            status=status.value if status else None,
            entry_type=entry_type.value if entry_type else None,
        )

    async def update_status(
        self,
        session: AsyncSession,
        user_id: str,
        entry_id: str,
        new_status: EntryStatus,
    ) -> Entry:
        if new_status is EntryStatus.CANON:
            await self._lock_active_owner(session, user_id)
        entry = await self._get_for_update(session, user_id, entry_id)
        current = EntryStatus(entry.status)
        if new_status not in ALLOWED_STATUS_TRANSITIONS[current]:
            raise ValidationAppError(
                "Invalid Entry status transition",
                {"from": current.value, "to": new_status.value},
            )

        if (
            new_status is EntryStatus.CANON
            and EntryType(entry.type) in SINGLE_CURRENT_ENTRY_TYPES
        ):
            existing = await self.repo.find_active_canon_for_update(
                session,
                user_id=user_id,
                scope_kind=entry.scope_kind,
                scope_id=entry.scope_id,
                entry_type=entry.type,
                subject_type=entry.subject_type,
                subject_id=entry.subject_id,
                exclude_entry_id=entry.id,
            )
            if existing is not None:
                raise ValidationAppError(
                    "Active canon already exists for this single-current Entry identity; "
                    "use supersede() to replace it",
                    {"existing_entry_id": existing.id, "type": entry.type},
                )

        entry.status = new_status.value
        now = utcnow()
        if new_status is EntryStatus.CANON:
            entry.accepted_at = now
        elif new_status is EntryStatus.REJECTED:
            entry.rejected_at = now
        await session.commit()
        await session.refresh(entry)
        return entry

    async def supersede(
        self,
        session: AsyncSession,
        user_id: str,
        current_entry_id: str,
        replacement_entry_id: str,
    ) -> tuple[Entry, Entry]:
        if current_entry_id == replacement_entry_id:
            raise ValidationAppError("An Entry cannot supersede itself")

        await self._lock_active_owner(session, user_id)
        locked: dict[str, Entry] = {}
        for entry_id in sorted((current_entry_id, replacement_entry_id)):
            locked[entry_id] = await self._get_for_update(session, user_id, entry_id)
        current = locked[current_entry_id]
        replacement = locked[replacement_entry_id]
        if current.status != EntryStatus.CANON.value:
            raise ValidationAppError("Only canon Entry can be superseded")
        if replacement.status != EntryStatus.PROPOSED.value:
            raise ValidationAppError("Replacement Entry must be proposed")
        if current.superseded_by_entry_id is not None:
            raise ValidationAppError("Canon Entry already has a replacement")
        if not self._compatible_for_supersession(current, replacement):
            raise ValidationAppError(
                "Replacement must have compatible scope, type, and subject identity"
            )
        await self._assert_acyclic(session, user_id, current.id, replacement)

        now = utcnow()
        replacement.status = EntryStatus.CANON.value
        replacement.accepted_at = now
        current.status = EntryStatus.SUPERSEDED.value
        current.superseded_by_entry_id = replacement.id
        current.superseded_at = now
        await session.commit()
        await session.refresh(current)
        await session.refresh(replacement)
        return current, replacement

    async def _assert_active_owner(self, session: AsyncSession, user_id: str) -> None:
        user = await session.get(User, user_id)
        if user is None or not user.is_active:
            raise NotFound("User not found")

    async def _lock_active_owner(self, session: AsyncSession, user_id: str) -> None:
        """Serialize canon lifecycle writes per owner on PostgreSQL.

        An identity-level ``FOR UPDATE`` query cannot lock the absence of a canon
        row. Locking the owner first closes that no-row race without a migration;
        SQLite ignores the clause and retains its single-writer behavior.
        """
        stmt = (
            select(User.id)
            .where(User.id == user_id, User.is_active.is_(True))
            .with_for_update()
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            raise NotFound("User not found")

    @staticmethod
    def _validate_creation_state(dto: EntryCreate) -> None:
        """Defend the write boundary even if internal code bypasses DTO revalidation."""
        if dto.status in {
            EntryStatus.CANON,
            EntryStatus.REJECTED,
            EntryStatus.SUPERSEDED,
        }:
            raise ValidationAppError(
                f"Entry cannot be created directly as {dto.status.value}"
            )
        if dto.provenance.capture_method is ProvenanceCaptureMethod.AI_EXTRACTED:
            if dto.status is not EntryStatus.PROPOSED:
                raise ValidationAppError("AI-extracted Entry must start proposed")
            if dto.confidence is None:
                raise ValidationAppError("AI-extracted Entry requires confidence")

    async def _get_for_update(
        self, session: AsyncSession, user_id: str, entry_id: str
    ) -> Entry:
        entry = await self.repo.get_for_update(session, entry_id, user_id=user_id)
        if entry is None:
            raise NotFound("Entry not found", {"id": entry_id})
        return entry

    async def _validate_scope(
        self,
        session: AsyncSession,
        user_id: str,
        scope_kind: EntryScope,
        scope_id: str | None,
    ) -> None:
        if scope_kind is EntryScope.USER:
            return
        if scope_kind is EntryScope.COLLECTION:
            # The legacy baseline has no Collection aggregate. Accepting an
            # unverified identifier would violate RFC-002 ownership isolation.
            raise ValidationAppError(
                "collection scope is unavailable until an owned Collection aggregate exists"
            )
        model = {
            EntryScope.WORK: Work,
            EntryScope.CHARACTER: Character,
            EntryScope.WORLD: World,
        }.get(scope_kind)
        if model is None or scope_id is None:
            raise ValidationAppError("Unsupported Entry scope")
        await self._assert_owned_record(session, model, scope_id, user_id, "scope_id")

    async def _validate_and_normalize_subject(
        self,
        session: AsyncSession,
        user_id: str,
        scope_kind: EntryScope,
        scope_id: str | None,
        subject_type: EntrySubjectType | None,
        subject_id: str | None,
        subject_data: dict[str, Any],
    ) -> tuple[str | None, dict[str, Any]]:
        if subject_type is None:
            return None, {}
        if subject_type is EntrySubjectType.CHARACTER_PAIR:
            character_ids = sorted(subject_data["character_ids"])
            for character_id in character_ids:
                await self._assert_owned_record(
                    session, Character, character_id, user_id, "subject.character_ids"
                )
            normalized = dict(subject_data)
            normalized["character_ids"] = character_ids
            return "|".join(character_ids), normalized

        model = {
            EntrySubjectType.WORK: Work,
            EntrySubjectType.CHAPTER: Chapter,
            EntrySubjectType.CHARACTER: Character,
            EntrySubjectType.WORLD: World,
        }[subject_type]
        record = await self._assert_owned_record(
            session, model, subject_id, user_id, "subject_id"
        )

        if scope_kind is EntryScope.WORK:
            if subject_type is EntrySubjectType.WORK and subject_id != scope_id:
                raise ValidationAppError("work subject must match work scope")
            if subject_type is EntrySubjectType.CHAPTER and record.work_id != scope_id:
                raise ValidationAppError("chapter subject must belong to work scope")
        if scope_kind is EntryScope.CHARACTER and subject_type is EntrySubjectType.CHARACTER:
            if subject_id != scope_id:
                raise ValidationAppError("character subject must match character scope")
        if scope_kind is EntryScope.WORLD and subject_type is EntrySubjectType.WORLD:
            if subject_id != scope_id:
                raise ValidationAppError("world subject must match world scope")
        return subject_id, dict(subject_data)

    async def _validate_provenance(
        self, session: AsyncSession, user_id: str, dto: EntryCreate
    ) -> None:
        provenance = dto.provenance
        if provenance.source_kind is ProvenanceSourceKind.USER:
            if provenance.source_id is not None and provenance.source_id != user_id:
                raise ValidationAppError("user provenance must reference the owner")
        elif provenance.source_kind in {
            ProvenanceSourceKind.CHAPTER,
            ProvenanceSourceKind.EDIT_DIFF,
        }:
            await self._assert_owned_record(
                session, Chapter, provenance.source_id, user_id, "provenance.source_id"
            )
        elif provenance.source_kind is ProvenanceSourceKind.CHAT_BOOKMARK:
            await self._assert_owned_record(
                session, Message, provenance.source_id, user_id, "provenance.source_id"
            )

    async def _validate_chapter_origin(
        self,
        session: AsyncSession,
        user_id: str,
        scope_kind: EntryScope,
        scope_id: str | None,
        chapter_id: str | None,
    ) -> None:
        if chapter_id is None:
            return
        chapter = await self._assert_owned_record(
            session, Chapter, chapter_id, user_id, "created_at_chapter_id"
        )
        if scope_kind is EntryScope.WORK and chapter.work_id != scope_id:
            raise ValidationAppError("created_at_chapter_id must belong to work scope")

    async def _assert_owned_record(
        self,
        session: AsyncSession,
        model: type[Any],
        record_id: str | None,
        user_id: str,
        field: str,
    ) -> Any:
        if record_id is None:
            raise ValidationAppError(f"{field} is required")
        record = await session.get(model, record_id)
        if (
            record is None
            or getattr(record, "user_id", None) != user_id
            or getattr(record, "deleted_at", None) is not None
        ):
            raise ValidationAppError(f"{field} must reference an owned active record")
        return record

    @staticmethod
    def _compatible_for_supersession(current: Entry, replacement: Entry) -> bool:
        return (
            current.user_id == replacement.user_id
            and current.scope_kind == replacement.scope_kind
            and current.scope_id == replacement.scope_id
            and current.type == replacement.type
            and current.subject_type == replacement.subject_type
            and current.subject_id == replacement.subject_id
            and current.subject_data == replacement.subject_data
        )

    async def _assert_acyclic(
        self,
        session: AsyncSession,
        user_id: str,
        current_entry_id: str,
        replacement: Entry,
    ) -> None:
        seen = {replacement.id}
        next_id = replacement.superseded_by_entry_id
        while next_id is not None:
            if next_id == current_entry_id or next_id in seen:
                raise ValidationAppError("Supersession relation must be acyclic")
            seen.add(next_id)
            linked = await self.repo.get(session, next_id, user_id=user_id)
            if linked is None:
                raise ValidationAppError("Supersession target must belong to the same owner")
            next_id = linked.superseded_by_entry_id
