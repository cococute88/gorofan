"""Async engine/session factory (design 8.6). Single DATABASE_URL switch.

SQLite gets WAL + foreign_keys=ON pragmas (design 8.1.4 / 8.16).
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings


def ensure_sqlite_dir(database_url: str) -> None:
    """Create the parent directory of a sqlite file DB if missing.

    A clean clone has no ``data/`` dir (it's gitignored); sqlite refuses to
    create the file's parent directory itself, so the first connection fails
    with ``unable to open database file``. The path is CWD-relative, matching
    sqlite3/aiosqlite's own resolution semantics.
    """
    if not database_url.startswith("sqlite"):
        return
    path = database_url.split("///", 1)[-1]
    if not path or path == ":memory:":
        return
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def create_engine(settings: Settings) -> AsyncEngine:
    connect_args: dict = {}
    if settings.is_sqlite:
        connect_args["check_same_thread"] = False
        ensure_sqlite_dir(settings.DATABASE_URL)
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        future=True,
        pool_pre_ping=not settings.is_sqlite,
        connect_args=connect_args,
    )
    if settings.is_sqlite:
        _enable_sqlite_pragmas(engine)
    return engine


def _enable_sqlite_pragmas(engine: AsyncEngine) -> None:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_pragmas(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def session_scope(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Context-style session generator. Rolls back on error, always closes (design 8.4.1)."""
    session = sessionmaker()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
