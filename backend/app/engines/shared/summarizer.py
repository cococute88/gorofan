"""Shared Summarizer (design 11.9 / CON-6).

Promoted to a shared component so MemoryEngine and NovelEngine reuse it without
importing each other (preserves single-direction dependency, design 2.3). Builds a
summary prompt via PromptEngine and calls the provider (non-stream).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.adapters.base import ProviderRequest
from app.adapters.registry import ProviderRegistry
from app.engines.prompt.engine import AssembleInput, PromptEngine

SUMMARY_TEMPLATE = (
    "당신은 장편 서사의 기록자다. 아래 대화/본문을 한국어로 간결하게 요약한다. "
    "등장인물의 결정·감정 변화·중요한 사실·미해결 떡밥을 보존하되 군더더기는 제거한다. "
    "이전 요약이 있으면 누적해 갱신한다."
)


@dataclass
class Summarizer:
    prompt_engine: PromptEngine
    registry: ProviderRegistry

    async def summarize_text(
        self,
        *,
        source_text: str,
        prev_summary: str | None,
        req: ProviderRequest,
    ) -> str:
        body = SUMMARY_TEMPLATE
        if prev_summary:
            body += f"\n\n[이전 요약]\n{prev_summary}"
        assembled = self.prompt_engine.assemble(
            AssembleInput(
                template_body=body,
                user_message=f"[요약 대상]\n{source_text}",
                context_window=req.context_window,
                max_tokens=req.max_tokens,
            )
        )
        provider = self.registry.get(req.provider)
        completion = await provider.chat(assembled, req)
        return completion.content.strip()
