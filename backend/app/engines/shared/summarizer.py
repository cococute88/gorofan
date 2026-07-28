"""Shared Summarizer (design 11.9 / CON-6).

Promoted to a shared component so MemoryEngine and NovelEngine reuse it without
importing each other (preserves single-direction dependency, design 2.3). Builds a
summary prompt via PromptEngine and calls the provider (non-stream).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.adapters.base import ProviderRequest
from app.adapters.registry import ProviderRegistry
from app.engines.prompt.assets import PromptAssetLoader
from app.engines.prompt.engine import AssembleInput, PromptEngine


@dataclass
class Summarizer:
    prompt_engine: PromptEngine
    registry: ProviderRegistry
    prompt_assets: PromptAssetLoader = field(default_factory=PromptAssetLoader)

    async def summarize_text(
        self,
        *,
        source_text: str,
        prev_summary: str | None,
        req: ProviderRequest,
    ) -> str:
        asset = self.prompt_assets.load("summary.rolling")
        body = asset.body
        if prev_summary:
            body += f"\n\n[이전 요약]\n{prev_summary}"
        assembled = self.prompt_engine.assemble(
            AssembleInput(
                template_body=body,
                prompt_asset_id=asset.asset_id,
                prompt_asset_version=asset.version,
                prompt_asset_sha256=asset.sha256,
                user_message=f"[요약 대상]\n{source_text}",
                context_window=req.context_window,
                max_tokens=req.max_tokens,
            )
        )
        provider = self.registry.get(req.provider)
        completion = await provider.chat(assembled, req)
        return completion.content.strip()
