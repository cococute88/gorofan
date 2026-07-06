"""ChatService — SSE streaming orchestration (design 8.5.2, 12).

Transaction stages:
  T1: persist user message + load context (short commit)
  T2: stream tokens (no DB session held)
  T3: persist assistant message exactly once (short commit)
  T4: enqueue background summary if needed (non-blocking)

Guarantees Property 4 (immutable, single save) and Property 9 (partial preservation).
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.base import StreamEvent
from app.adapters.registry import ProviderRegistry
from app.config import Settings
from app.core.errors import AppError, Conflict, NotFound
from app.core.jobs import Job, JobQueue
from app.core.logging import get_logger
from app.core.pagination import Page, PageParams
from app.engines.chat.engine import ChatEngine
from app.models.character import Character, Persona
from app.models.chat import ChatSession, Message
from app.models.world import Lorebook, LoreEntry, World
from app.schemas.chat import ChatCreate, MessageCreate
from app.services.provider_resolve import resolve_provider_request

log = get_logger("chat")

# Per-session in-memory serialization (single worker MVP, design 12.12 / 8.7.4 caveat).
_active_streams: set[str] = set()


class ChatService:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        settings: Settings,
        registry: ProviderRegistry,
        chat_engine: ChatEngine,
        job_queue: JobQueue,
    ) -> None:
        self.sm = sessionmaker
        self.settings = settings
        self.registry = registry
        self.engine = chat_engine
        self.jobs = job_queue

    async def create_session(self, user_id: str, dto: ChatCreate) -> ChatSession:
        async with self.sm() as s:
            character = await s.get(Character, dto.character_id)
            if character is None or character.user_id != user_id:
                raise NotFound("Character not found")
            chat = ChatSession(user_id=user_id, **dto.model_dump())
            s.add(chat)
            await s.flush()
            # seed greeting as first assistant message (design 12.6)
            if character.greeting:
                s.add(
                    Message(
                        chat_session_id=chat.id,
                        user_id=user_id,
                        role="assistant",
                        content=character.greeting,
                        token_count=0,
                        status="complete",
                    )
                )
            await s.commit()
            await s.refresh(chat)
            return chat

    async def list_sessions(self, user_id: str, page: PageParams) -> Page[ChatSession]:
        async with self.sm() as s:
            stmt = (
                select(ChatSession)
                .where(ChatSession.user_id == user_id)
                .order_by(desc(ChatSession.updated_at))
                .limit(page.limit)
            )
            rows = list((await s.execute(stmt)).scalars().all())
            return Page(items=rows, next_cursor=None)

    async def get_messages(self, user_id: str, chat_id: str, page: PageParams) -> Page[Message]:
        async with self.sm() as s:
            await self._owned_session(s, user_id, chat_id)
            stmt = (
                select(Message)
                .where(Message.chat_session_id == chat_id, Message.is_active.is_(True))
                .order_by(desc(Message.created_at), desc(Message.id))
                .limit(page.limit + 1)
            )
            if page.before:
                before_msg = await s.get(Message, page.before)
                if before_msg is not None:
                    stmt = stmt.where(Message.created_at < before_msg.created_at)
            rows = list((await s.execute(stmt)).scalars().all())
            rows = list(reversed(rows[: page.limit]))
            return Page(items=rows, next_cursor=None)

    async def stream_message(
        self, user_id: str, chat_id: str, dto: MessageCreate
    ) -> AsyncIterator[StreamEvent]:
        if chat_id in _active_streams:
            raise Conflict("A response is already streaming for this session")
        _active_streams.add(chat_id)
        try:
            async for evt in self._stream_impl(user_id, chat_id, dto, regenerate=False):
                yield evt
        finally:
            _active_streams.discard(chat_id)

    async def regenerate(self, user_id: str, chat_id: str) -> AsyncIterator[StreamEvent]:
        if chat_id in _active_streams:
            raise Conflict("A response is already streaming for this session")
        _active_streams.add(chat_id)
        try:
            async for evt in self._stream_impl(user_id, chat_id, None, regenerate=True):
                yield evt
        finally:
            _active_streams.discard(chat_id)

    async def _stream_impl(
        self, user_id: str, chat_id: str, dto: MessageCreate | None, *, regenerate: bool
    ) -> AsyncIterator[StreamEvent]:
        # --- T1: persist user message + assemble prompt ---
        async with self.sm() as s:
            chat = await self._owned_session(s, user_id, chat_id)
            character = await s.get(Character, chat.character_id)
            persona = await s.get(Persona, chat.persona_id) if chat.persona_id else None
            world = await s.get(World, character.world_id) if character and character.world_id else None
            lore = await self._load_lore(s, world.id) if world else []
            parent_id: str | None = None

            if regenerate:
                last_assistant = await self._last_active_assistant(s, chat_id)
                if last_assistant is not None:
                    last_assistant.is_active = False
                    parent_id = last_assistant.parent_message_id
                user_text = await self._last_user_text(s, chat_id)
            else:
                assert dto is not None
                user_msg = Message(
                    chat_session_id=chat_id,
                    user_id=user_id,
                    role="user",
                    content=dto.content,
                    token_count=self.engine.prompt_engine.tok.count(dto.content),
                    status="complete",
                )
                s.add(user_msg)
                await s.flush()
                parent_id = user_msg.id
                user_text = dto.content

            req = await resolve_provider_request(
                s, self.settings, self.registry,
                user_id=user_id, model_config_id=chat.model_config_id, purpose="chat",
            )
            prompt = await self.engine.assemble_for_chat(
                s, chat_id=chat_id, character=character, persona=persona,
                world=world, lore_entries=lore, user_message=user_text, req=req,
            )
            await s.commit()

        # --- T2: stream (no DB session held) ---
        buffer = ""
        finish_reason = "stop"
        try:
            async for evt in self.engine.stream(prompt, req):
                if evt.delta:
                    buffer += evt.delta
                yield evt
        except AppError as exc:
            await self._persist_assistant(user_id, chat_id, parent_id, buffer, "partial")
            yield StreamEvent(event="error", code=exc.code, message=exc.message)
            return

        # --- T3: persist assistant message exactly once ---
        msg = await self._persist_assistant(user_id, chat_id, parent_id, buffer, "complete", finish_reason)
        yield StreamEvent(
            event="done", message_id=msg.id, token_count=msg.token_count, finish_reason=finish_reason
        )

        # --- T4: background summary if needed (non-blocking) ---
        await self._maybe_enqueue_summary(user_id, chat_id, req, msg.id)

    async def _persist_assistant(
        self, user_id, chat_id, parent_id, content, status, finish_reason="stop"  # noqa: ANN001
    ) -> Message:
        async with self.sm() as s:
            msg = Message(
                chat_session_id=chat_id,
                user_id=user_id,
                parent_message_id=parent_id,
                role="assistant",
                content=content,
                token_count=self.engine.prompt_engine.tok.count(content),
                status=status,
                meta={"finish_reason": finish_reason, "partial": status == "partial"},
            )
            s.add(msg)
            await s.commit()
            await s.refresh(msg)
            return msg

    async def force_summarize(self, user_id: str, chat_id: str) -> None:
        async with self.sm() as s:
            chat = await self._owned_session(s, user_id, chat_id)
            req = await resolve_provider_request(
                s, self.settings, self.registry,
                user_id=user_id, model_config_id=chat.model_config_id, purpose="summary",
            )
        await self.jobs.enqueue(
            Job(
                kind="summarize",
                payload={"chat_id": chat_id, "user_id": user_id, "req": _req_dict(req)},
                idempotency_key=f"summarize:{chat_id}:force",
            )
        )

    async def _maybe_enqueue_summary(self, user_id, chat_id, req, last_msg_id) -> None:  # noqa: ANN001
        async with self.sm() as s:
            need = await self.engine.memory_engine.needs_summary(s, chat_id, req.context_window)
        if need:
            await self.jobs.enqueue(
                Job(
                    kind="summarize",
                    payload={"chat_id": chat_id, "user_id": user_id, "req": _req_dict(req)},
                    idempotency_key=f"summarize:{chat_id}:{last_msg_id}",
                )
            )

    # ----- helpers -----
    async def _owned_session(self, s: AsyncSession, user_id: str, chat_id: str) -> ChatSession:
        chat = await s.get(ChatSession, chat_id)
        if chat is None or chat.user_id != user_id:
            raise NotFound("Chat session not found")
        return chat

    async def _load_lore(self, s: AsyncSession, world_id: str) -> list[LoreEntry]:
        stmt = (
            select(LoreEntry)
            .join(Lorebook, Lorebook.id == LoreEntry.lorebook_id)
            .where(Lorebook.world_id == world_id, LoreEntry.enabled.is_(True))
        )
        return list((await s.execute(stmt)).scalars().all())

    async def _last_active_assistant(self, s, chat_id) -> Message | None:  # noqa: ANN001
        stmt = (
            select(Message)
            .where(
                Message.chat_session_id == chat_id,
                Message.role == "assistant",
                Message.is_active.is_(True),
            )
            .order_by(desc(Message.created_at))
            .limit(1)
        )
        return (await s.execute(stmt)).scalars().first()

    async def _last_user_text(self, s, chat_id) -> str:  # noqa: ANN001
        stmt = (
            select(Message)
            .where(Message.chat_session_id == chat_id, Message.role == "user")
            .order_by(desc(Message.created_at))
            .limit(1)
        )
        m = (await s.execute(stmt)).scalars().first()
        return m.content if m else ""


def _req_dict(req) -> dict:  # noqa: ANN001
    return {
        "provider": req.provider,
        "model_name": req.model_name,
        "base_url": req.base_url,
        "api_key": req.api_key,
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
        "context_window": req.context_window,
    }
