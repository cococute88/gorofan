"""Provider Adapter neutral contracts (design 13.5).

The PromptEngine emits a provider-neutral ``AssembledPrompt``; adapters render it
to each provider's wire format (design 9.13). These DTOs live here so both the
Engine (which calls adapters) and the Adapter layer can share them without the
adapter importing the engine (preserves single-direction dependency, design 2.3).
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal, Protocol

Role = Literal["system", "user", "assistant"]


@dataclass
class ChatMessage:
    role: Role
    content: str


@dataclass
class AssembledPrompt:
    """Provider-neutral assembled prompt (design 9.5)."""

    messages: list[ChatMessage]
    token_count: int = 0
    system: str | None = None  # extracted system text (for Anthropic/Gemini, design 9.13)
    trace: dict = field(default_factory=dict)


@dataclass
class Completion:
    content: str
    token_count: int
    finish_reason: str


@dataclass
class ModelCapability:
    context_window: int
    max_output_tokens: int
    supports_streaming: bool = True
    system_role: Literal["message", "param", "instruction"] = "message"
    supports_tools: bool = False
    tokenizer_hint: str = "approx"  # "tiktoken-cl100k" | "approx"
    safety_ratio: float = 0.08


@dataclass
class StreamEvent:
    """Maps 1:1 to the Phase 6.4 SSE protocol."""

    event: Literal["token", "done", "error"]
    delta: str | None = None
    message_id: str | None = None
    token_count: int | None = None
    finish_reason: str | None = None
    code: str | None = None
    message: str | None = None


@dataclass
class ProviderRequest:
    """Resolved per-call provider parameters (decrypted key stays here, never logged)."""

    provider: str
    model_name: str
    base_url: str | None
    api_key: str | None
    temperature: float
    max_tokens: int
    context_window: int


class LLMProvider(Protocol):
    def stream_chat(
        self, prompt: AssembledPrompt, req: ProviderRequest
    ) -> AsyncIterator[str]: ...

    async def chat(self, prompt: AssembledPrompt, req: ProviderRequest) -> Completion: ...

    def capabilities(self, model: str) -> ModelCapability: ...
