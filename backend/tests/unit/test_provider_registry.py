"""Provider-neutral retry boundaries exercised by the Gemini direct path."""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from app.adapters.anthropic import AnthropicAdapter
from app.adapters.base import AssembledPrompt, Completion, ModelCapability, ProviderRequest
from app.adapters.gemini import GeminiAdapter
from app.adapters.ollama import OllamaAdapter
from app.adapters.openai_compat import OpenAICompatAdapter
from app.adapters.registry import ProviderRegistry, build_provider_registry
from app.core.errors import ProviderRateLimited


def _request() -> ProviderRequest:
    return ProviderRequest(
        provider="gemini",
        model_name="gemini-3.8-flash",
        base_url=None,
        api_key="opaque",
        temperature=0.7,
        max_tokens=100,
        context_window=1_048_576,
    )


class _RateLimitedThenSuccess:
    def __init__(self) -> None:
        self.calls = 0

    async def stream_chat(
        self, prompt: AssembledPrompt, req: ProviderRequest
    ) -> AsyncIterator[str]:
        self.calls += 1
        if self.calls < 3:
            raise ProviderRateLimited("limited")
        yield "완료"

    async def chat(self, prompt: AssembledPrompt, req: ProviderRequest) -> Completion:
        raise NotImplementedError

    def capabilities(self, model: str) -> ModelCapability:
        return ModelCapability(1_048_576, 65_536)


class _FailsAfterFirstToken(_RateLimitedThenSuccess):
    async def stream_chat(
        self, prompt: AssembledPrompt, req: ProviderRequest
    ) -> AsyncIterator[str]:
        self.calls += 1
        yield "부분"
        raise ProviderRateLimited("mid-stream")


@pytest.mark.asyncio
async def test_registry_retries_rate_limit_only_before_first_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _RateLimitedThenSuccess()
    registry = ProviderRegistry()
    registry.register("gemini", lambda: adapter)

    async def no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr("app.adapters.registry.asyncio.sleep", no_sleep)
    tokens = [
        token
        async for token in registry.stream_with_resilience(
            AssembledPrompt(messages=[]), _request()
        )
    ]

    assert tokens == ["완료"]
    assert adapter.calls == 3


@pytest.mark.asyncio
async def test_registry_never_restarts_after_first_token() -> None:
    adapter = _FailsAfterFirstToken()
    registry = ProviderRegistry()
    registry.register("gemini", lambda: adapter)
    tokens: list[str] = []

    with pytest.raises(ProviderRateLimited, match="mid-stream"):
        async for token in registry.stream_with_resilience(
            AssembledPrompt(messages=[]), _request()
        ):
            tokens.append(token)

    assert tokens == ["부분"]
    assert adapter.calls == 1


def test_built_registry_keeps_existing_provider_factories() -> None:
    registry = build_provider_registry()

    assert {"openai", "anthropic", "gemini", "ollama"}.issubset(
        registry.list_providers()
    )
    assert isinstance(registry.get("openai"), OpenAICompatAdapter)
    assert isinstance(registry.get("anthropic"), AnthropicAdapter)
    assert isinstance(registry.get("gemini"), GeminiAdapter)
    assert isinstance(registry.get("ollama"), OllamaAdapter)


@pytest.mark.asyncio
async def test_gemini_failure_never_falls_back_to_another_provider() -> None:
    gemini = _RateLimitedThenSuccess()
    fallback = _RateLimitedThenSuccess()
    registry = ProviderRegistry()
    registry.register("gemini", lambda: gemini)
    registry.register("openai", lambda: fallback)

    with pytest.raises(ProviderRateLimited, match="limited"):
        async for _token in registry.stream_with_resilience(
            AssembledPrompt(messages=[]), _request(), max_retries=0
        ):
            pass

    assert gemini.calls == 1
    assert fallback.calls == 0
