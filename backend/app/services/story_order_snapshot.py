"""Transaction-local consistent story-order snapshot setup."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict


async def begin_story_order_snapshot(session: AsyncSession) -> None:
    """Start a repeatable read view before any generation-preparation query.

    PostgreSQL needs an explicit transaction-local isolation override because
    its default READ COMMITTED level can expose a reorder between statements.
    SQLite's legacy transaction mode does not begin a transaction for SELECT,
    so an explicit BEGIN is required to pin its WAL read snapshot.
    """

    if session.in_transaction():
        raise Conflict("Story-order snapshot must start before preparation reads")
    bind = session.get_bind()
    dialect = bind.dialect.name
    try:
        if dialect == "postgresql":
            await session.connection(
                execution_options={"isolation_level": "REPEATABLE READ"}
            )
        elif dialect == "sqlite":
            await session.connection(
                execution_options={"isolation_level": "SERIALIZABLE"}
            )
            await session.execute(text("BEGIN"))
        else:
            raise Conflict(
                "Story-order snapshot is unsupported for this database",
                {"dialect": dialect},
            )
    except Conflict:
        raise
    except Exception as exc:  # noqa: BLE001
        raise Conflict("Unable to establish a consistent story-order snapshot") from exc
