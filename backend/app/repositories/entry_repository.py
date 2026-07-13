"""Owner-scoped persistence access for RFC-002 Entries."""
from __future__ import annotations

import builtins

from sqlalchemy import and_, false, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entry import Entry


class EntryRepository:
    async def add(self, session: AsyncSession, entry: Entry) -> Entry:
        session.add(entry)
        await session.flush()
        return entry

    async def get(self, session: AsyncSession, entry_id: str, *, user_id: str) -> Entry | None:
        stmt = select(Entry).where(Entry.id == entry_id, Entry.user_id == user_id)
        return (await session.execute(stmt)).scalars().first()

    async def get_for_update(
        self, session: AsyncSession, entry_id: str, *, user_id: str
    ) -> Entry | None:
        """Lock one owner-scoped Entry for a lifecycle mutation.

        PostgreSQL emits ``FOR UPDATE``; SQLite safely ignores the clause and
        retains its single-writer behavior.
        """
        stmt = (
            select(Entry)
            .where(Entry.id == entry_id, Entry.user_id == user_id)
            .with_for_update()
        )
        return (await session.execute(stmt)).scalars().first()

    async def find_active_canon_for_update(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        scope_kind: str,
        scope_id: str | None,
        entry_type: str,
        subject_type: str | None,
        subject_id: str | None,
        exclude_entry_id: str,
    ) -> Entry | None:
        """Lock an existing canon with the same persisted identity, if any."""
        stmt = select(Entry).where(
            Entry.user_id == user_id,
            Entry.scope_kind == scope_kind,
            Entry.scope_id.is_(None) if scope_id is None else Entry.scope_id == scope_id,
            Entry.type == entry_type,
            (
                Entry.subject_type.is_(None)
                if subject_type is None
                else Entry.subject_type == subject_type
            ),
            Entry.subject_id.is_(None) if subject_id is None else Entry.subject_id == subject_id,
            Entry.status == "canon",
            Entry.id != exclude_entry_id,
        )
        stmt = stmt.order_by(Entry.id).limit(1).with_for_update()
        return (await session.execute(stmt)).scalars().first()

    async def list(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        scope_kind: str | None = None,
        scope_id: str | None = None,
        status: str | None = None,
        entry_type: str | None = None,
    ) -> list[Entry]:
        stmt = select(Entry).where(Entry.user_id == user_id)
        if scope_kind is not None:
            stmt = stmt.where(Entry.scope_kind == scope_kind)
        if scope_id is not None:
            stmt = stmt.where(Entry.scope_id == scope_id)
        if status is not None:
            stmt = stmt.where(Entry.status == status)
        if entry_type is not None:
            stmt = stmt.where(Entry.type == entry_type)
        stmt = stmt.order_by(Entry.created_at, Entry.id)
        return list((await session.execute(stmt)).scalars().all())

    async def list_retrieval_candidates(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        scopes: builtins.list[tuple[str, str | None]],
        statuses: builtins.list[str],
        entry_types: builtins.list[str] | None,
        subjects: builtins.list[tuple[str, str]],
    ) -> builtins.list[Entry]:
        """Return owner-rooted candidates for ``EntryService.retrieve()`` only.

        The service layer still excludes orphaned and soft-deleted scope or
        subject anchors before ranking. Callers must not treat this repository
        method's rows as complete retrieval results or bypass the service.
        """
        scope_predicates = [
            and_(
                Entry.scope_kind == scope_kind,
                Entry.scope_id.is_(None) if scope_id is None else Entry.scope_id == scope_id,
            )
            for scope_kind, scope_id in scopes
        ]
        stmt = select(Entry).where(
            Entry.user_id == user_id,
            or_(*scope_predicates) if scope_predicates else false(),
            Entry.status.in_(statuses),
        )
        if entry_types is not None:
            stmt = stmt.where(Entry.type.in_(entry_types))
        if subjects:
            stmt = stmt.where(
                or_(
                    *(
                        and_(Entry.subject_type == subject_type, Entry.subject_id == subject_id)
                        for subject_type, subject_id in subjects
                    )
                )
            )
        stmt = stmt.order_by(Entry.id)
        return list((await session.execute(stmt)).scalars().all())
