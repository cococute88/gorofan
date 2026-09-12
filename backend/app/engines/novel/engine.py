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
from app.engines.novel.generation_preparation import (
    GenerationPreparation,
    GenerationSectionKind,
    thaw_mapping,
)
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
        preparation: GenerationPreparation,
        *,
        req: ProviderRequest,
    ) -> AssembledPrompt:
        """Render an immutable preparation through the existing PromptEngine.

        AOS-1 deliberately keeps the legacy provider-visible prompt contract.
        Work metadata is now explicit in the preparation, but its admission to
        the production template belongs to a later, separately reviewed prompt
        change.  Everything the current continuation prompt already used is
        rendered byte-for-byte through the same PromptEngine path here.
        """

        asset = self.prompt_assets.load("novel.continue")
        cap = self.registry.capabilities(req.provider, req.model_name)
        # Preserve the legacy runtime character-context wrapper around the asset body.
        char_lines = [
            item.content
            for item in preparation.section(GenerationSectionKind.CHARACTERS).items
            if item.evidence.source_type == "character"
        ]
        body = asset.body
        if char_lines:
            body += "\n\n[등장인물]\n" + "\n".join(char_lines)
        current_items = preparation.section(GenerationSectionKind.CURRENT_CHAPTER).items
        current_context = current_items[0].content if current_items else ""
        instruction = "\n\n".join(
            item.content
            for item in preparation.section(GenerationSectionKind.INSTRUCTION).items
        )
        prepared_entry_blocks: list[PromptBlock] = []
        for prepared_block in preparation.entry_blocks:
            block = prepared_block.to_prompt_block()
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
                world=preparation.world,
                lore_entries=list(preparation.lore),
                chapter_prior_summaries=[
                    summary.content for summary in preparation.prior_summaries
                ],
                chapter_prior_summary_indexes=[
                    summary.chapter_index for summary in preparation.prior_summaries
                ],
                history=[],
                entry_blocks=prepared_entry_blocks,
                entry_context_trace=thaw_mapping(preparation.entry_context_trace),
                user_message=current_context or None,
                instruction=instruction,
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
