"""Retriever Protocol + KeywordRetriever (design 10.5, 10.12).

MVP keyword matching. EmbeddingRetriever (RAG) is a drop-in replacement using the
same Protocol with an optional MEMORY.embedding column — schema-non-breaking (FUT-2).
"""
from __future__ import annotations

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import Memory


class Retriever(Protocol):
    async def search(
        self, session: AsyncSession, chat_id: str, query: str, k: int
    ) -> list[Memory]: ...


class KeywordRetriever:
    async def search(
        self, session: AsyncSession, chat_id: str, query: str, k: int
    ) -> list[Memory]:
        stmt = select(Memory).where(Memory.chat_session_id == chat_id)
        rows = list((await session.execute(stmt)).scalars().all())
        if not query:
            return rows[:k]
        q_tokens = {t for t in query.lower().split() if len(t) > 1}
        scored = []
        for m in rows:
            content = (m.content or "").lower()
            overlap = sum(1 for t in q_tokens if t in content)
            scored.append((overlap, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:k]]
