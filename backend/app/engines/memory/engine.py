"""MemoryEngine (design Phase 10).

Builds short-term (recent window) + long-term (ranked summaries) context, decides
when to summarize, and produces rolling summaries. Summary runs in background
(non-blocking, design 8.8). Guarantees Property 5 (cover_up_to validity/monotonicity).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import ProviderRequest
from app.engines.memory.retriever import KeywordRetriever, Retriever
from app.engines.shared.summarizer import Summarizer
from app.models.chat import Memory, Message

SHORT_WINDOW = 12
RETRIEVE_K = 6
SUMMARY_TOKEN_THRESHOLD_RATIO = 0.5  # of context_window
TAU_SECONDS = 60 * 60 * 24  # recency decay
W_RECENCY, W_RELEVANCE, W_PRIORITY = 0.4, 0.4, 0.2
_KIND_WEIGHT = {"fact": 1.0, "event": 0.8, "summary": 0.6}


@dataclass
class MemoryContext:
    short_term: list[Message] = field(default_factory=list)
    long_term: list[Memory] = field(default_factory=list)
    version: int = 0
    token_estimate: int = 0


@dataclass
class MemoryEngine:
    summarizer: Summarizer
    retriever: Retriever = field(default_factory=KeywordRetriever)

    async def build_memory_context(
        self, session: AsyncSession, chat_id: str, *, query: str | None, budget_hint: int
    ) -> MemoryContext:
        short = await self._recent_messages(session, chat_id, SHORT_WINDOW)
        candidates = await self.retriever.search(session, chat_id, query or "", RETRIEVE_K)
        ranked = self._rank(candidates, query)
        long_term = self._select_within_budget(ranked, budget_hint)
        version = await self._memory_version(session, chat_id)
        est = sum(m.token_count for m in short) + sum(m.token_count for m in long_term)
        return MemoryContext(short_term=short, long_term=long_term, version=version, token_estimate=est)

    async def needs_summary(
        self, session: AsyncSession, chat_id: str, context_window: int
    ) -> bool:
        last = await self._latest_summary(session, chat_id)
        cover_id = last.cover_up_to_message_id if last else None
        stmt = select(func.coalesce(func.sum(Message.token_count), 0)).where(
            Message.chat_session_id == chat_id, Message.is_active.is_(True)
        )
        if cover_id:
            cover_msg = await session.get(Message, cover_id)
            if cover_msg is not None:
                stmt = stmt.where(Message.created_at > cover_msg.created_at)
        total = (await session.execute(stmt)).scalar_one()
        return int(total) >= int(context_window * SUMMARY_TOKEN_THRESHOLD_RATIO)

    async def maybe_summarize(
        self, session: AsyncSession, chat_id: str, req: ProviderRequest, user_id: str
    ) -> Memory | None:
        prev = await self._latest_summary(session, chat_id)
        messages = await self._unsummarized(session, chat_id, prev)
        if not messages:
            return None
        last = messages[-1]
        source = "\n".join(f"{m.role}: {m.content}" for m in messages)
        text = await self.summarizer.summarize_text(
            source_text=source, prev_summary=prev.content if prev else None, req=req
        )
        # Property 5: cover_up_to points to a real message in this session, monotonic.
        version = (prev.version + 1) if prev else 1
        mem = Memory(
            chat_session_id=chat_id,
            user_id=user_id,
            kind="summary",
            content=text,
            cover_up_to_message_id=last.id,
            version=version,
            token_count=self.summarizer.prompt_engine.tok.count(text),
        )
        session.add(mem)
        return mem

    # ----- ranking (design 10.8) -----
    def _rank(self, candidates: list[Memory], query: str | None) -> list[Memory]:
        now = datetime.now(timezone.utc)
        q_tokens = {t for t in (query or "").lower().split() if len(t) > 1}

        def score(m: Memory) -> float:
            created = m.created_at or now
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            dt = max(0.0, (now - created).total_seconds())
            recency = math.exp(-dt / TAU_SECONDS)
            content = (m.content or "").lower()
            relevance = (
                sum(1 for t in q_tokens if t in content) / len(q_tokens) if q_tokens else 0.0
            )
            priority = _KIND_WEIGHT.get(m.kind, 0.5)
            return W_RECENCY * recency + W_RELEVANCE * relevance + W_PRIORITY * priority

        return sorted(candidates, key=score, reverse=True)

    def _select_within_budget(self, ranked: list[Memory], budget_hint: int) -> list[Memory]:
        out: list[Memory] = []
        used = 0
        for m in ranked:
            if used + m.token_count > budget_hint:
                break
            out.append(m)
            used += m.token_count
        return out

    # ----- queries -----
    async def _recent_messages(self, session, chat_id, limit) -> list[Message]:  # noqa: ANN001
        stmt = (
            select(Message)
            .where(Message.chat_session_id == chat_id, Message.is_active.is_(True))
            .order_by(desc(Message.created_at), desc(Message.id))
            .limit(limit)
        )
        rows = list((await session.execute(stmt)).scalars().all())
        return list(reversed(rows))

    async def _latest_summary(self, session, chat_id) -> Memory | None:  # noqa: ANN001
        stmt = (
            select(Memory)
            .where(Memory.chat_session_id == chat_id, Memory.kind == "summary")
            .order_by(desc(Memory.version))
            .limit(1)
        )
        return (await session.execute(stmt)).scalars().first()

    async def _memory_version(self, session, chat_id) -> int:  # noqa: ANN001
        stmt = select(func.coalesce(func.max(Memory.version), 0)).where(
            Memory.chat_session_id == chat_id
        )
        return int((await session.execute(stmt)).scalar_one())

    async def _unsummarized(self, session, chat_id, prev) -> list[Message]:  # noqa: ANN001
        stmt = (
            select(Message)
            .where(Message.chat_session_id == chat_id, Message.is_active.is_(True))
            .order_by(Message.created_at, Message.id)
        )
        if prev and prev.cover_up_to_message_id:
            cover = await session.get(Message, prev.cover_up_to_message_id)
            if cover is not None:
                stmt = stmt.where(Message.created_at > cover.created_at)
        return list((await session.execute(stmt)).scalars().all())
