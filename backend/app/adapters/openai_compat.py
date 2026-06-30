"""OpenAI-compatible adapter (design 13.4).

Covers OpenAI / DeepSeek / Qwen / OpenRouter and (via subclass) Ollama. Normalizes
the SSE token stream to neutral deltas (design 13.6) and maps errors to Phase 6.1
codes (design 13.9).
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from app.adapters.base import (
    AssembledPrompt,
    Completion,
    ModelCapability,
    ProviderRequest,
)
from app.core.errors import ProviderError, ProviderRateLimited

# Coarse capability registry; real values can be refined per model (design 13.10).
_KNOWN_WINDOWS = {
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "deepseek-chat": 64000,
    "qwen-max": 32000,
}


class OpenAICompatAdapter:
    provider_name = "openai"
    default_base_url = "https://api.openai.com/v1"

    def _base_url(self, req: ProviderRequest) -> str:
        return (req.base_url or self.default_base_url).rstrip("/")

    def _headers(self, req: ProviderRequest) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if req.api_key:
            headers["Authorization"] = f"Bearer {req.api_key}"
        return headers

    def _payload(self, prompt: AssembledPrompt, req: ProviderRequest, stream: bool) -> dict:
        messages = [{"role": m.role, "content": m.content} for m in prompt.messages]
        return {
            "model": req.model_name,
            "messages": messages,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
            "stream": stream,
        }

    def capabilities(self, model: str) -> ModelCapability:
        window = _KNOWN_WINDOWS.get(model, 8192)
        return ModelCapability(
            context_window=window,
            max_output_tokens=4096,
            supports_streaming=True,
            system_role="message",
            tokenizer_hint="tiktoken-cl100k" if self.provider_name == "openai" else "approx",
            safety_ratio=0.02 if self.provider_name == "openai" else 0.08,
        )

    async def chat(self, prompt: AssembledPrompt, req: ProviderRequest) -> Completion:
        url = f"{self._base_url(req)}/chat/completions"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await self._post(client, url, self._headers(req), self._payload(prompt, req, False))
            data = resp.json()
        choice = data["choices"][0]
        return Completion(
            content=choice["message"]["content"],
            token_count=data.get("usage", {}).get("completion_tokens", 0),
            finish_reason=choice.get("finish_reason", "stop"),
        )

    async def stream_chat(
        self, prompt: AssembledPrompt, req: ProviderRequest
    ) -> AsyncIterator[str]:
        url = f"{self._base_url(req)}/chat/completions"
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST", url, headers=self._headers(req), json=self._payload(prompt, req, True)
            ) as resp:
                self._raise_for_status(resp.status_code)
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue  # tolerate partial/keepalive lines (design 13.13)
                    delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                    if delta:
                        yield delta

    async def _post(self, client, url, headers, payload):  # noqa: ANN001
        try:
            resp = await client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise ProviderError(f"provider request failed: {type(exc).__name__}") from exc
        self._raise_for_status(resp.status_code)
        return resp

    @staticmethod
    def _raise_for_status(status: int) -> None:
        if status == 429:
            raise ProviderRateLimited("provider rate limited", {"retry_after": 5})
        if status >= 400:
            # Do not leak provider body (may contain key hints) — generalize (design 13.9).
            raise ProviderError(f"provider returned status {status}")
