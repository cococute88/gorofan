"""BaseRepository[T] — scoped CRUD + cursor pagination (design 8.3).

No commit here (Service owns transactions, design 8.5). All reads are scoped by
user_id (Property 1). Soft-deletable models are filtered to deleted_at IS NULL by
default.
"""
from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import Select, and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, PageParams, decode_cursor, encode_cursor
from app.db.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    model: type[T]

    def __init__(self, model: type[T]) -> None:
        self.model = model

    async def add(self, session: AsyncSession, entity: T) -> T:
        session.add(entity)
        await session.flush()
        return entity

    async def get(self, session: AsyncSession, id_: str, *, user_id: str) -> T | None:
        stmt = self._scoped(select(self.model).where(self.model.id == id_), user_id)
        stmt = self._active(stmt)
        return (await session.execute(stmt)).scalars().first()

    async def update(self, session: AsyncSession, entity: T, patch: dict) -> T:
        for key, value in patch.items():
            if value is not None and hasattr(entity, key):
                setattr(entity, key, value)
        await session.flush()
        return entity

    async def soft_delete(self, session: AsyncSession, entity: T) -> None:
        if hasattr(entity, "deleted_at"):
            from app.db.base import utcnow

            entity.deleted_at = utcnow()
            await session.flush()
        else:
            await self.hard_delete(session, entity)

    async def hard_delete(self, session: AsyncSession, entity: T) -> None:
        await session.delete(entity)
        await session.flush()

    async def list_page(
        self, session: AsyncSession, *, user_id: str, page: PageParams, extra=None
    ) -> Page[T]:
        stmt = self._scoped(select(self.model), user_id)
        stmt = self._active(stmt)
        if extra is not None:
            stmt = extra(stmt)
        stmt = stmt.order_by(self.model.created_at, self.model.id)
        if page.cursor:
            decoded = decode_cursor(page.cursor)
            if decoded:
                created, id_ = decoded
                stmt = stmt.where(
                    (self.model.created_at > created)
                    | and_(self.model.created_at == created, self.model.id > id_)
                )
        rows = list((await session.execute(stmt.limit(page.limit + 1))).scalars().all())
        next_cursor = None
        if len(rows) > page.limit:
            last = rows[page.limit - 1]
            next_cursor = encode_cursor(str(last.created_at), last.id)
            rows = rows[: page.limit]
        return Page(items=rows, next_cursor=next_cursor)

    # ----- scoping helpers (design 8.3.1) -----
    def _scoped(self, stmt: Select, user_id: str) -> Select:
        if hasattr(self.model, "user_id"):
            return stmt.where(self.model.user_id == user_id)
        return stmt

    def _active(self, stmt: Select) -> Select:
        if hasattr(self.model, "deleted_at"):
            return stmt.where(self.model.deleted_at.is_(None))
        return stmt
