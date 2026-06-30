"""NovelEngine (design Phase 11).

Builds story context (prior chapter summaries + characters + world + lore) and
streams "continue writing". target_words is a soft target (CJK is non-linear,
design 11.6); actual end is delegated to the provider finish_reason.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.adapters.base import AssembledPrompt, ProviderRequest, StreamEvent
from app.adapters.registry import ProviderRegistry
from app.engines.prompt.engine import AssembleInput, PromptEngine

DEFAULT_NOVEL_TEMPLATE = (
    "당신은 숙련된 소설가다. 주어진 세계관·등장인물·이전 줄거리에 일관되게, 몰입감 있는 "
    "한국어 산문으로 다음 분량을 이어쓴다. 시점과 문체를 유지하고 갑작스러운 설정 변경을 피한다."
)


def words_to_tokens(words: int) -> int:
    # rough soft conversion; korean ~1.6 tokens/word heuristic
    return max(64, int(words * 1.6))


@dataclass
class ChapterContext:
    work: object
    current_chapter: object
    prior_summaries: list[str]
    characters: list
    world: object | None
    lore_entries: list


@dataclass
class NovelEngine:
    prompt_engine: PromptEngine
    registry: ProviderRegistry

    def assemble_continue(
        self,
        ctx: ChapterContext,
        *,
        instruction: str,
        req: ProviderRequest,
    ) -> AssembledPrompt:
        cap = self.registry.capabilities(req.provider, req.model_name)
        # blend characters' personalities into the system body
        char_lines = [
            f"- {getattr(c, 'name', '')}: {getattr(c, 'personality', '')} / 말투: {getattr(c, 'speech_style', '')}"
            for c in ctx.characters
        ]
        body = DEFAULT_NOVEL_TEMPLATE
        if char_lines:
            body += "\n\n[등장인물]\n" + "\n".join(char_lines)
        tail = getattr(ctx.current_chapter, "content_text", "") or ""
        tail = tail[-1200:]
        return self.prompt_engine.assemble(
            AssembleInput(
                template_body=body,
                character=None,
                world=ctx.world,
                lore_entries=ctx.lore_entries or [],
                chapter_prior_summaries=ctx.prior_summaries,
                history=[],
                user_message=(f"[현재 챕터 끝부분]\n{tail}" if tail else None),
                instruction=instruction or "자연스럽게 다음 장면을 이어써라.",
                context_window=req.context_window,
                max_tokens=req.max_tokens,
                safety_ratio=cap.safety_ratio,
            )
        )

    async def continue_stream(
        self, prompt: AssembledPrompt, req: ProviderRequest
    ) -> AsyncIterator[StreamEvent]:
        async for token in self.registry.stream_with_resilience(prompt, req):
            yield StreamEvent(event="token", delta=token)
