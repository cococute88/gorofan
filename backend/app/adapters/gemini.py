"""Gemini adapter (design 13.4, 9.13).

Maps the system block to ``systemInstruction`` and turns to ``contents``.
Streams ``streamGenerateContent`` chunks normalized to neutral deltas.
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


class GeminiAdapter:
    provider_name = "gemini"
    default_base_url = "https://generativelanguage.googleapis.com/v1beta"

    def _contents(self, prompt: AssembledPrompt) -> dict:
        system = prompt.system or "\n".join(
            m.content for m in prompt.messages if m.role == "system"
        )
        contents = []
        for m in prompt.messages:
            if m.role == "system":
                continue
            role = "user" if m.role == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m.content}]})
        body: dict = {"contents": contents}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        return body

    def capabilities(self, model: str) -> ModelCapability:
        return ModelCapability(
            context_window=1000000 if "1.5" in model else 32000,
            max_output_tokens=8192,
            supports_streaming=True,
            system_role="instruction",
            tokenizer_hint="approx",
            safety_ratio=0.08,
        )

    def _url(self, req: ProviderRequest, method: str) -> str:
        base = (req.base_url or self.default_base_url).rstrip("/")
        return f"{base}/models/{req.model_name}:{method}?key={req.api_key or ''}"

    async def chat(self, prompt: AssembledPrompt, req: ProviderRequest) -> Completion:
        body = self._contents(prompt)
        body["generationConfig"] = {
            "temperature": req.temperature,
            "maxOutputTokens": req.max_tokens,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                resp = await client.post(self._url(req, "generateContent"), json=body)
            except httpx.HTTPError as exc:
                raise ProviderError(f"gemini request failed: {type(exc).__name__}") from exc
            self._raise_for_status(resp.status_code)
            data = resp.json()
        cand = (data.get("candidates") or [{}])[0]
        text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
        return Completion(content=text, token_count=0, finish_reason=cand.get("finishReason", "stop"))

    async def stream_chat(
        self, prompt: AssembledPrompt, req: ProviderRequest
    ) -> AsyncIterator[str]:
        body = self._contents(prompt)
        body["generationConfig"] = {
            "temperature": req.temperature,
            "maxOutputTokens": req.max_tokens,
        }
        url = self._url(req, "streamGenerateContent") + "&alt=sse"
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", url, json=body) as resp:
                self._raise_for_status(resp.status_code)
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    raw = line[len("data:") :].strip()
                    try:
                        evt = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    for cand in evt.get("candidates", []):
                        for part in cand.get("content", {}).get("parts", []):
                            if part.get("text"):
                                yield part["text"]

    @staticmethod
    def _raise_for_status(status: int) -> None:
        if status == 429:
            raise ProviderRateLimited("gemini rate limited", {"retry_after": 5})
        if status >= 400:
            raise ProviderError(f"gemini returned status {status}")
