"""Anthropic adapter (design 13.4, 9.13).

Anthropic uses a top-level ``system`` parameter rather than a system message, and
emits ``content_block_delta`` events. We normalize the stream to neutral deltas.
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

_WINDOWS = {
    "claude-3-5-sonnet": 200000,
    "claude-3-5-haiku": 200000,
    "claude-3-opus": 200000,
}


class AnthropicAdapter:
    provider_name = "anthropic"
    default_base_url = "https://api.anthropic.com/v1"

    def _headers(self, req: ProviderRequest) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": req.api_key or "",
            "anthropic-version": "2023-06-01",
        }

    def _payload(self, prompt: AssembledPrompt, req: ProviderRequest, stream: bool) -> dict:
        # split system out (design 9.13)
        system = prompt.system or ""
        turns = [
            {"role": m.role, "content": m.content}
            for m in prompt.messages
            if m.role in ("user", "assistant")
        ]
        if not system:
            system = "\n".join(m.content for m in prompt.messages if m.role == "system")
        payload = {
            "model": req.model_name,
            "messages": turns,
            "max_tokens": req.max_tokens,
            "temperature": req.temperature,
            "stream": stream,
        }
        if system:
            payload["system"] = system
        return payload

    def capabilities(self, model: str) -> ModelCapability:
        window = next((w for k, w in _WINDOWS.items() if model.startswith(k)), 200000)
        return ModelCapability(
            context_window=window,
            max_output_tokens=8192,
            supports_streaming=True,
            system_role="param",
            tokenizer_hint="approx",
            safety_ratio=0.08,
        )

    async def chat(self, prompt: AssembledPrompt, req: ProviderRequest) -> Completion:
        url = f"{(req.base_url or self.default_base_url).rstrip('/')}/messages"
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                resp = await client.post(
                    url, headers=self._headers(req), json=self._payload(prompt, req, False)
                )
            except httpx.HTTPError as exc:
                raise ProviderError(f"anthropic request failed: {type(exc).__name__}") from exc
            self._raise_for_status(resp.status_code)
            data = resp.json()
        text = "".join(block.get("text", "") for block in data.get("content", []))
        return Completion(
            content=text,
            token_count=data.get("usage", {}).get("output_tokens", 0),
            finish_reason=data.get("stop_reason", "stop"),
        )

    async def stream_chat(
        self, prompt: AssembledPrompt, req: ProviderRequest
    ) -> AsyncIterator[str]:
        url = f"{(req.base_url or self.default_base_url).rstrip('/')}/messages"
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST", url, headers=self._headers(req), json=self._payload(prompt, req, True)
            ) as resp:
                self._raise_for_status(resp.status_code)
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    raw = line[len("data:") :].strip()
                    try:
                        evt = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if evt.get("type") == "content_block_delta":
                        delta = evt.get("delta", {}).get("text")
                        if delta:
                            yield delta
                    elif evt.get("type") == "message_stop":
                        break

    @staticmethod
    def _raise_for_status(status: int) -> None:
        if status == 429:
            raise ProviderRateLimited("anthropic rate limited", {"retry_after": 5})
        if status >= 400:
            raise ProviderError(f"anthropic returned status {status}")
