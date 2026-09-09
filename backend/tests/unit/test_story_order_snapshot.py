"""Database-specific setup contract for the preparation read snapshot."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict
from app.services.story_order_snapshot import begin_story_order_snapshot


class _Session:
    def __init__(self, dialect: str, *, active: bool = False) -> None:
        self.dialect = dialect
        self.active = active
        self.connection_options: list[dict[str, str]] = []
        self.statements: list[str] = []

    def in_transaction(self) -> bool:
        return self.active

    def get_bind(self):  # noqa: ANN201
        return SimpleNamespace(dialect=SimpleNamespace(name=self.dialect))

    async def connection(self, *, execution_options):  # noqa: ANN001, ANN201
        self.connection_options.append(dict(execution_options))

    async def execute(self, statement):  # noqa: ANN001, ANN201
        self.statements.append(str(statement))


@pytest.mark.asyncio
async def test_postgresql_uses_transaction_local_repeatable_read() -> None:
    session = _Session("postgresql")

    await begin_story_order_snapshot(cast(AsyncSession, cast(Any, session)))

    assert session.connection_options == [{"isolation_level": "REPEATABLE READ"}]
    assert session.statements == []


@pytest.mark.asyncio
async def test_sqlite_explicitly_begins_serializable_read_snapshot() -> None:
    session = _Session("sqlite")

    await begin_story_order_snapshot(cast(AsyncSession, cast(Any, session)))

    assert session.connection_options == [{"isolation_level": "SERIALIZABLE"}]
    assert session.statements == ["BEGIN"]


@pytest.mark.asyncio
async def test_snapshot_setup_fails_closed_after_any_prior_read() -> None:
    session = _Session("postgresql", active=True)

    with pytest.raises(Conflict, match="before preparation reads"):
        await begin_story_order_snapshot(cast(AsyncSession, cast(Any, session)))

    assert session.connection_options == []
