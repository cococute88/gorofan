"""Ollama adapter (design 13.4).

Reuses the OpenAI-compatible endpoint (`/v1`) exposed by Ollama. Enables fully
offline operation (NFR-8). Default base URL targets a local daemon.
"""
from __future__ import annotations

from app.adapters.base import ModelCapability
from app.adapters.openai_compat import OpenAICompatAdapter


class OllamaAdapter(OpenAICompatAdapter):
    provider_name = "ollama"
    default_base_url = "http://localhost:11434/v1"

    def capabilities(self, model: str) -> ModelCapability:
        return ModelCapability(
            context_window=8192,
            max_output_tokens=2048,
            supports_streaming=True,
            system_role="message",
            tokenizer_hint="approx",
            safety_ratio=0.1,
        )
