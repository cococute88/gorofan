"""Background summarize job handler (design 8.8, 10.7).

Registered with the JobQueue at startup. Runs MemoryEngine.maybe_summarize in its
own short transaction. Failures never break the chat flow (BR-6).
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.base import ProviderRequest
from app.engines.memory.engine import MemoryEngine


def make_summarize_handler(
    sessionmaker: async_sessionmaker[AsyncSession], memory_engine: MemoryEngine
):
    async def handler(payload: dict) -> None:
        chat_id = payload["chat_id"]
        user_id = payload["user_id"]
        req = ProviderRequest(**payload["req"])
        async with sessionmaker() as s:
            mem = await memory_engine.maybe_summarize(s, chat_id, req, user_id)
            if mem is not None:
                await s.commit()

    return handler
