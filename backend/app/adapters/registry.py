"""Provider registry/factory (design 13.4, 8.17).

New providers are added by registering a factory — zero core changes (FR-AI-2/FUT-4).
Also implements resilient streaming with retry + optional fallback (design 13.7/13.8).
"""
from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator, Callable

from app.adapters.anthropic import AnthropicAdapter
from app.adapters.base import (
    AssembledPrompt,
    LLMProvider,
    ModelCapability,
    ProviderRequest,
)
from app.adapters.gemini import GeminiAdapter
from app.adapters.ollama import OllamaAdapter
from app.adapters.openai_compat import OpenAICompatAdapter
from app.core.errors import ProviderError, ProviderRateLimited
from app.core.logging import get_logger

log = get_logger("provider")

ProviderFactory = Callable[[], LLMProvider]


class ProviderRegistry:
    def __init__(self, max_concurrency: int = 4) -> None:
        self._factories: dict[str, ProviderFactory] = {}
        self._semaphore = asyncio.Semaphore(max_concurrency)

    def register(self, provider_type: str, factory: ProviderFactory) -> None:
        self._factories[provider_type] = factory

    def get(self, provider_type: str) -> LLMProvider:
        factory = self._factories.get(provider_type)
        if factory is None:
            # OpenAI-compatible fallback for unknown providers with custom base_url.
            factory = self._factories["openai"]
        return factory()

    def capabilities(self, provider_type: str, model: str) -> ModelCapability:
        return self.get(provider_type).capabilities(model)

    def list_providers(self) -> list[str]:
        return sorted(self._factories.keys())

    async def stream_with_resilience(
        self, prompt: AssembledPrompt, req: ProviderRequest, max_retries: int = 2
    ) -> AsyncIterator[str]:
        """Retry before first token only; preserve partial after streaming starts (13.7)."""
        provider = self.get(req.provider)
        attempt = 0
        async with self._semaphore:
            while True:
                started = False
                try:
                    async for token in provider.stream_chat(prompt, req):
                        started = True
                        yield token
                    return
                except ProviderRateLimited:
                    if started or attempt >= max_retries:
                        raise
                    attempt += 1
                    await asyncio.sleep(min(2**attempt, 10) + random.random())
                except ProviderError:
                    if started or attempt >= max_retries:
                        raise
                    attempt += 1
                    await asyncio.sleep(min(2**attempt, 10) + random.random())


def build_provider_registry(max_concurrency: int = 4) -> ProviderRegistry:
    reg = ProviderRegistry(max_concurrency=max_concurrency)
    reg.register("openai", OpenAICompatAdapter)
    reg.register("deepseek", OpenAICompatAdapter)
    reg.register("qwen", OpenAICompatAdapter)
    reg.register("openrouter", OpenAICompatAdapter)
    reg.register("anthropic", AnthropicAdapter)
    reg.register("gemini", GeminiAdapter)
    reg.register("ollama", OllamaAdapter)
    return reg
