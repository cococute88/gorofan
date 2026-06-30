"""ChatEngine (design Phase 12).

Assembles a single turn (Memory + Prompt) and relays Adapter tokens as StreamEvents.
DB writes/commits are owned by the service (design 8.5). This engine is pure
orchestration over engines/adapters.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import AssembledPrompt, ProviderRequest, StreamEvent
from app.adapters.registry import ProviderRegistry
from app.engines.memory.engine import MemoryEngine
from app.engines.prompt.engine import AssembleInput, PromptEngine

DEFAULT_CHAT_TEMPLATE = (
    "당신은 {{char}}라는 캐릭터로서 사용자와 대화한다. 캐릭터의 성격과 말투를 일관되게 "
    "유지하고, 세계관과 기억을 존중하며 자연스러운 한국어로 응답한다."
)


@dataclass
class ChatEngine:
    prompt_engine: PromptEngine
    memory_engine: MemoryEngine
    registry: ProviderRegistry

    async def assemble_for_chat(
        self,
        session: AsyncSession,
        *,
        chat_id: str,
        character,
        persona,
        world,
        lore_entries,
        user_message: str | None,
        req: ProviderRequest,
        template_body: str | None = None,
    ) -> AssembledPrompt:
        budget_hint = max(256, int(req.context_window * 0.4))
        mem = await self.memory_engine.build_memory_context(
            session, chat_id, query=user_message, budget_hint=budget_hint
        )
        cap = self.registry.capabilities(req.provider, req.model_name)
        return self.prompt_engine.assemble(
            AssembleInput(
                template_body=template_body or DEFAULT_CHAT_TEMPLATE,
                character=character,
                persona=persona,
                world=world,
                lore_entries=lore_entries or [],
                memory_short=mem.short_term,
                memory_long=mem.long_term,
                history=[],
                user_message=user_message,
                context_window=req.context_window,
                max_tokens=req.max_tokens,
                safety_ratio=cap.safety_ratio,
            )
        )

    async def stream(
        self, prompt: AssembledPrompt, req: ProviderRequest
    ) -> AsyncIterator[StreamEvent]:
        async for token in self.registry.stream_with_resilience(prompt, req):
            yield StreamEvent(event="token", delta=token)
