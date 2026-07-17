"""Owner-safe Entry Store persistence and retrieval boundary (RFC-002/RFC-003).

This service owns validated persistence, lifecycle transitions, atomic
supersession, Review Card transition helpers, and the read-only Store retrieval
seam. HTTP adaptation and Context Assembly remain separate boundaries.
"""
from __future__ import annotations

import builtins
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound, ValidationAppError
from app.db.base import utcnow
from app.models.character import Character
from app.models.chat import ChatSession, Message
from app.models.entry import Entry
from app.models.novel import Chapter, Work
from app.models.user import User
from app.models.world import World
from app.repositories.entry_repository import EntryRepository
from app.schemas.entry import (
    EntryCreate,
    EntryProvenance,
    EntryRetrievalResult,
    EntryRetrievalTrace,
    EntryRetrieveRequest,
    EntryReviewEdit,
    EntryScope,
    EntryStatus,
    EntrySubjectType,
    EntryType,
    ProvenanceCaptureMethod,
    ProvenanceSourceKind,
)
from app.services.entry_retrieval import (
    RETRIEVAL_POLICY_VERSION,
    rank_entries,
    select_entries,
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

    async def list_review_entries(
        self, session: AsyncSession, user_id: str
    ) -> builtins.list[Entry]:
        """Return only the authenticated owner's pending Review Cards."""
        await self._assert_active_owner(session, user_id)
        return await self.list(session, user_id, status=EntryStatus.PROPOSED)

    async def get_review_entry(
        self, session: AsyncSession, user_id: str, entry_id: str
    ) -> Entry:
        entry = await self.get(session, user_id, entry_id)
        self._require_proposed_review(entry)
        return entry

    async def edit_review_entry(
        self,
        session: AsyncSession,
        user_id: str,
        entry_id: str,
        dto: EntryReviewEdit,
    ) -> Entry:
        """Edit a proposed Entry without allowing lifecycle or ownership changes."""
        entry = await self._get_for_update(session, user_id, entry_id)
        self._require_proposed_review(entry)
        for field, value in dto.model_dump(exclude_unset=True).items():
            setattr(entry, field, value)
        entry.provenance = {
            **entry.provenance,
            "capture_method": ProvenanceCaptureMethod.HUMAN_EDITED.value,
        }
        await session.commit()
        await session.refresh(entry)
        return entry

    async def accept_review_entry(
        self, session: AsyncSession, user_id: str, entry_id: str
    ) -> Entry:
        return await self._transition_status(
            session,
            user_id,
            entry_id,
            EntryStatus.CANON,
            require_proposed_review=True,
            validate_acceptance_anchors=True,
        )

    async def reject_review_entry(
        self, session: AsyncSession, user_id: str, entry_id: str
    ) -> Entry:
        return await self._transition_status(
            session,
            user_id,
            entry_id,
            EntryStatus.REJECTED,
            require_proposed_review=True,
        )

    async def retrieve(
        self, session: AsyncSession, request: EntryRetrieveRequest
    ) -> EntryRetrievalResult:
        """Select an owner-safe, scope-bound slice of the Entry Store."""
        await self._assert_active_owner(session, request.user_id)
        statuses = set(request.status_filters or [EntryStatus.CANON])
        if request.include_rejected:
            statuses.add(EntryStatus.REJECTED)
        if request.include_superseded:
            statuses.add(EntryStatus.SUPERSEDED)

        scopes = [
            (selector.scope_kind.value, selector.scope_id)
            for selector in request.scopes
            if selector.scope_kind is not EntryScope.CHAT_PRIVATE
        ]
        subjects = [
            (subject.subject_type.value, subject.persisted_subject_id)
            for subject in request.subject_filters
        ]
        candidates = await self.repo.list_retrieval_candidates(
            session,
            user_id=request.user_id,
            scopes=scopes,
            statuses=sorted(status.value for status in statuses),
            entry_types=(
                sorted(entry_type.value for entry_type in request.entry_types)
                if request.entry_types is not None
                else None
            ),
            subjects=subjects,
        )

        candidates, orphaned_ids = await self._exclude_orphaned_candidates(
            session, request.user_id, candidates
        )
        ranked = rank_entries(candidates, request)
        selected, budget_rejected, limit_rejected = select_entries(ranked, request)
        return EntryRetrievalResult(
            items=selected,
            total_estimated_tokens=sum(item.estimated_tokens for item in selected),
            requested_budget=request.budget,
            policy_version=RETRIEVAL_POLICY_VERSION,
            trace=EntryRetrievalTrace(
                excluded_orphaned_entry_ids=orphaned_ids,
                budget_rejected_entry_ids=budget_rejected,
                limit_rejected_entry_ids=limit_rejected,
            ),
        )

    async def update_status(
        self,
        session: AsyncSession,
        user_id: str,
        entry_id: str,
        new_status: EntryStatus,
    ) -> Entry:
        return await self._transition_status(session, user_id, entry_id, new_status)

    async def _transition_status(
        self,
        session: AsyncSession,
        user_id: str,
        entry_id: str,
        new_status: EntryStatus,
        *,
        require_proposed_review: bool = False,
        validate_acceptance_anchors: bool = False,
    ) -> Entry:
        if new_status is EntryStatus.CANON:
            await self._lock_active_owner(session, user_id)
        entry = await self._get_for_update(session, user_id, entry_id)
        if require_proposed_review:
            self._require_proposed_review(entry)
        current = EntryStatus(entry.status)
        if new_status not in ALLOWED_STATUS_TRANSITIONS[current]:
            raise ValidationAppError(
                "Invalid Entry status transition",
                {"from": current.value, "to": new_status.value},
            )

        if validate_acceptance_anchors:
            await self._validate_acceptance_anchors(session, user_id, entry)

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

    @staticmethod
    def _require_proposed_review(entry: Entry) -> None:
        if entry.status != EntryStatus.PROPOSED.value:
            raise ValidationAppError(
                "Entry is not proposed for review",
                {"entry_id": entry.id, "status": entry.status},
            )

    async def _validate_acceptance_anchors(
        self, session: AsyncSession, user_id: str, entry: Entry
    ) -> None:
        """Recheck persisted owner/liveness anchors immediately before acceptance."""
        live_entries, _ = await self._exclude_orphaned_candidates(
            session, user_id, [entry]
        )
        if not live_entries:
            raise ValidationAppError(
                "Proposed Entry has a missing, inaccessible, or soft-deleted scope/subject anchor",
                {"entry_id": entry.id},
            )

        try:
            provenance = EntryProvenance.model_validate(entry.provenance)
        except PydanticValidationError as exc:
            raise ValidationAppError("Proposed Entry has invalid provenance") from exc

        source_kind = provenance.source_kind
        source_id = provenance.source_id
        if source_kind is ProvenanceSourceKind.USER:
            if source_id is not None and source_id != user_id:
                raise ValidationAppError("Entry provenance no longer belongs to the owner")
        elif source_kind in {
            ProvenanceSourceKind.CHAPTER,
            ProvenanceSourceKind.EDIT_DIFF,
        }:
            await self._assert_active_chapter_anchor(
                session, user_id, source_id, "provenance.source_id"
            )
        elif source_kind is ProvenanceSourceKind.CHAT_BOOKMARK:
            if not isinstance(source_id, str):
                raise ValidationAppError("provenance.source_id is required")
            stmt = (
                select(Message.id)
                .join(ChatSession, ChatSession.id == Message.chat_session_id)
                .where(
                    Message.id == source_id,
                    Message.user_id == user_id,
                    ChatSession.user_id == user_id,
                )
            )
            if (await session.execute(stmt)).scalar_one_or_none() is None:
                raise ValidationAppError(
                    "provenance.source_id must reference an owned active record"
                )

        if entry.created_at_chapter_id is not None:
            await self._assert_active_chapter_anchor(
                session,
                user_id,
                entry.created_at_chapter_id,
                "created_at_chapter_id",
            )

    @staticmethod
    async def _assert_active_chapter_anchor(
        session: AsyncSession,
        user_id: str,
        chapter_id: object,
        field: str,
    ) -> None:
        if not isinstance(chapter_id, str):
            raise ValidationAppError(f"{field} is required")
        stmt = (
            select(Chapter.id)
            .join(Work, Work.id == Chapter.work_id)
            .where(
                Chapter.id == chapter_id,
                Chapter.user_id == user_id,
                Work.user_id == user_id,
                Work.deleted_at.is_(None),
            )
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            raise ValidationAppError(f"{field} must reference an owned active record")

    async def _exclude_orphaned_candidates(
        self, session: AsyncSession, user_id: str, entries: builtins.list[Entry]
    ) -> tuple[builtins.list[Entry], builtins.list[str]]:
        """Pre-rank filter for missing, deleted, or owner-invisible anchors."""
        work_ids = {
            value
            for entry in entries
            for value in (
                entry.scope_id if entry.scope_kind == EntryScope.WORK.value else None,
                entry.subject_id
                if entry.subject_type == EntrySubjectType.WORK.value
                else None,
            )
            if value is not None
        }
        character_ids = {
            value
            for entry in entries
            for value in self._entry_character_anchor_ids(entry)
        }
        world_ids = {
            value
            for entry in entries
            for value in (
                entry.scope_id if entry.scope_kind == EntryScope.WORLD.value else None,
                entry.subject_id
                if entry.subject_type == EntrySubjectType.WORLD.value
                else None,
            )
            if value is not None
        }
        chapter_ids = {
            entry.subject_id
            for entry in entries
            if entry.subject_type == EntrySubjectType.CHAPTER.value
            and entry.subject_id is not None
        }

        active_work_ids = await self._active_ids(
            session, Work, user_id, work_ids, soft_deletable=True
        )
        active_character_ids = await self._active_ids(
            session, Character, user_id, character_ids, soft_deletable=True
        )
        active_world_ids = await self._active_ids(
            session, World, user_id, world_ids, soft_deletable=True
        )
        active_chapter_work_ids: dict[str, str] = {}
        if chapter_ids:
            stmt = (
                select(Chapter.id, Chapter.work_id)
                .join(Work, Work.id == Chapter.work_id)
                .where(
                    Chapter.id.in_(chapter_ids),
                    Chapter.user_id == user_id,
                    Work.user_id == user_id,
                    Work.deleted_at.is_(None),
                )
            )
            active_chapter_work_ids = dict((await session.execute(stmt)).tuples().all())

        included: builtins.list[Entry] = []
        excluded: builtins.list[str] = []
        for entry in entries:
            if self._anchors_are_live(
                entry,
                active_work_ids=active_work_ids,
                active_character_ids=active_character_ids,
                active_world_ids=active_world_ids,
                active_chapter_work_ids=active_chapter_work_ids,
            ):
                included.append(entry)
            else:
                excluded.append(entry.id)
        return included, excluded

    @staticmethod
    async def _active_ids(
        session: AsyncSession,
        model: type[Any],
        user_id: str,
        record_ids: set[str],
        *,
        soft_deletable: bool,
    ) -> set[str]:
        if not record_ids:
            return set()
        stmt = select(model.id).where(model.id.in_(record_ids), model.user_id == user_id)
        if soft_deletable:
            stmt = stmt.where(model.deleted_at.is_(None))
        return set((await session.execute(stmt)).scalars().all())

    @staticmethod
    def _entry_character_anchor_ids(entry: Entry) -> set[str]:
        if entry.subject_type == EntrySubjectType.CHARACTER.value and entry.subject_id:
            return {entry.subject_id}
        if entry.subject_type == EntrySubjectType.CHARACTER_PAIR.value:
            values = (entry.subject_data or {}).get("character_ids")
            if isinstance(values, list):
                return {value for value in values if isinstance(value, str)}
        if entry.scope_kind == EntryScope.CHARACTER.value and entry.scope_id:
            return {entry.scope_id}
        return set()

    @staticmethod
    def _anchors_are_live(
        entry: Entry,
        *,
        active_work_ids: set[str],
        active_character_ids: set[str],
        active_world_ids: set[str],
        active_chapter_work_ids: dict[str, str],
    ) -> bool:
        scope_live = {
            EntryScope.USER.value: entry.scope_id is None,
            EntryScope.WORK.value: entry.scope_id in active_work_ids,
            EntryScope.CHARACTER.value: entry.scope_id in active_character_ids,
            EntryScope.WORLD.value: entry.scope_id in active_world_ids,
            EntryScope.COLLECTION.value: False,
        }.get(entry.scope_kind, False)
        if not scope_live:
            return False
        if entry.subject_type is None:
            return True
        if entry.subject_type == EntrySubjectType.WORK.value:
            return entry.subject_id in active_work_ids and (
                entry.scope_kind != EntryScope.WORK.value
                or entry.subject_id == entry.scope_id
            )
        if entry.subject_type == EntrySubjectType.CHAPTER.value:
            subject_work_id = active_chapter_work_ids.get(entry.subject_id or "")
            return subject_work_id is not None and (
                entry.scope_kind != EntryScope.WORK.value
                or subject_work_id == entry.scope_id
            )
        if entry.subject_type == EntrySubjectType.CHARACTER.value:
            return entry.subject_id in active_character_ids and (
                entry.scope_kind != EntryScope.CHARACTER.value
                or entry.subject_id == entry.scope_id
            )
        if entry.subject_type == EntrySubjectType.WORLD.value:
            return entry.subject_id in active_world_ids and (
                entry.scope_kind != EntryScope.WORLD.value
                or entry.subject_id == entry.scope_id
            )
        if entry.subject_type == EntrySubjectType.CHARACTER_PAIR.value:
            values = (entry.subject_data or {}).get("character_ids")
            return (
                isinstance(values, list)
                and len(values) == 2
                and all(isinstance(value, str) for value in values)
                and len(set(values)) == 2
                and entry.subject_id == "|".join(sorted(values))
                and all(value in active_character_ids for value in values)
            )
        return False

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
