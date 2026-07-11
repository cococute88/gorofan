"""Owner-scoped persistence access for RFC-002 Entries."""
from __future__ import annotations

from sqlalchemy import select
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
