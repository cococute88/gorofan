"""NovelEngine (design Phase 11).

Builds story context (prior chapter summaries + characters + world + lore) and
streams "continue writing". target_words is a soft target (CJK is non-linear,
design 11.6); actual end is delegated to the provider finish_reason.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field, replace

from app.adapters.base import AssembledPrompt, ProviderRequest, StreamEvent
from app.adapters.registry import ProviderRegistry
from app.engines.prompt.assets import PromptAssetLoader
from app.engines.prompt.blocks import PromptBlock
from app.engines.prompt.engine import AssembleInput, PromptEngine


def words_to_tokens(words: int) -> int:
    # rough soft conversion; korean ~1.6 tokens/word heuristic
    return max(64, int(words * 1.6))


@dataclass
class ChapterContext:
    work: object
    current_chapter: object
    prior_summaries: list[str]
    prior_summary_chapter_indexes: tuple[int, ...]
    characters: list
    world: object | None
    lore_entries: list
    substantive_legacy_summary_chapter_ids: tuple[str, ...] = ()


@dataclass
class NovelEngine:
    prompt_engine: PromptEngine
    registry: ProviderRegistry
    prompt_assets: PromptAssetLoader = field(default_factory=PromptAssetLoader)

    def assemble_continue(
        self,
        ctx: ChapterContext,
        *,
        instruction: str,
        req: ProviderRequest,
        entry_blocks: list[PromptBlock] | None = None,
        entry_context_trace: dict[str, object] | None = None,
    ) -> AssembledPrompt:
        asset = self.prompt_assets.load("novel.continue")
        cap = self.registry.capabilities(req.provider, req.model_name)
        # Preserve the legacy runtime character-context wrapper around the asset body.
        char_lines = [
            f"- {getattr(c, 'name', '')}: {getattr(c, 'personality', '')} / 말투: {getattr(c, 'speech_style', '')}"
            for c in ctx.characters
        ]
        body = asset.body
        if char_lines:
            body += "\n\n[등장인물]\n" + "\n".join(char_lines)
        tail = getattr(ctx.current_chapter, "content_text", "") or ""
        tail = tail[-1200:]
        if len(ctx.prior_summaries) != len(ctx.prior_summary_chapter_indexes):
            raise ValueError("Legacy chapter summary chronology evidence is incomplete")
        prepared_entry_blocks: list[PromptBlock] = []
        for block in entry_blocks or []:
            metadata = dict(block.metadata)
            if metadata.get("entry_type") == "story.summary":
                chronology = metadata.get("story_summary_chronology")
                if not isinstance(chronology, dict):
                    raise ValueError("Entry story summary chronology evidence is missing")
                source_index = chronology.get("source_chapter_index")
                if not isinstance(source_index, int) or isinstance(source_index, bool):
                    raise ValueError("Entry story summary source position is missing")
                metadata.update(
                    prepared_render_group="story_summary",
                    prepared_render_order=source_index,
                )
                block = replace(block, metadata=metadata)
            prepared_entry_blocks.append(block)
        return self.prompt_engine.assemble(
            AssembleInput(
                template_body=body,
                prompt_asset_id=asset.asset_id,
                prompt_asset_version=asset.version,
                prompt_asset_sha256=asset.sha256,
                character=None,
                world=ctx.world,
                lore_entries=ctx.lore_entries or [],
                chapter_prior_summaries=ctx.prior_summaries,
                chapter_prior_summary_indexes=list(ctx.prior_summary_chapter_indexes),
                history=[],
                entry_blocks=prepared_entry_blocks,
                entry_context_trace=entry_context_trace,
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
