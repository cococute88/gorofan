"""Gemini adapter (design 13.4, 9.13).

Maps the provider-neutral system block to ``systemInstruction`` and conversation
turns to ``contents``. ``generateContent`` and ``streamGenerateContent`` remain
the existing wire contract; provider responses are normalized to plain text.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import quote

import httpx

from app.adapters.base import (
    AssembledPrompt,
    Completion,
    ModelCapability,
    ProviderRequest,
)
from app.core.errors import ProviderError, ProviderRateLimited

# Verified against Google AI for Developers on 2026-09-12. Keep exact model
# authorities here; future/unknown names deliberately receive the conservative
# fallback rather than inheriting a guessed family capacity.
_MODEL_CAPABILITIES: dict[str, tuple[int, int]] = {
    "gemini-3.8-flash": (1_048_576, 65_536),
    "gemini-3.7-flash": (1_048_576, 65_536),
    "gemini-3.6-flash": (1_048_576, 65_536),
    "gemini-3.5-flash": (1_048_576, 65_536),
    "gemini-3.5-flash-lite": (1_048_576, 65_536),
    "gemini-3.1-flash-lite": (1_048_576, 65_536),
    "gemini-2.5-flash": (1_048_576, 65_536),
    "gemini-2.5-flash-lite": (1_048_576, 65_536),
    "gemini-2.5-pro": (1_048_576, 65_536),
}
_UNKNOWN_CONTEXT_WINDOW = 32_768
_UNKNOWN_MAX_OUTPUT_TOKENS = 8_192

_BLOCKED_FINISH_REASONS = {
    "SAFETY",
    "RECITATION",
    "LANGUAGE",
    "BLOCKLIST",
    "PROHIBITED_CONTENT",
    "SPII",
    "IMAGE_SAFETY",
}
_SUCCESS_FINISH_REASONS = {"", "STOP", "MAX_TOKENS"}


class GeminiAdapter:
    provider_name = "gemini"
    default_base_url = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        """Accept an optional transport so tests never need external network access."""

        self._transport = transport

    def _contents(self, prompt: AssembledPrompt) -> dict[str, Any]:
        system = prompt.system or "\n".join(
            message.content for message in prompt.messages if message.role == "system"
        )
        contents = []
        for message in prompt.messages:
            if message.role == "system":
                continue
            role = "user" if message.role == "user" else "model"
            contents.append({"role": role, "parts": [{"text": message.content}]})
        body: dict[str, Any] = {"contents": contents}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        return body

    def capabilities(self, model: str) -> ModelCapability:
        context_window, max_output_tokens = _MODEL_CAPABILITIES.get(
            model,
            (_UNKNOWN_CONTEXT_WINDOW, _UNKNOWN_MAX_OUTPUT_TOKENS),
        )
        return ModelCapability(
            context_window=context_window,
            max_output_tokens=max_output_tokens,
            supports_streaming=True,
            system_role="instruction",
            tokenizer_hint="approx",
            safety_ratio=0.08,
        )

    def _url(self, req: ProviderRequest, method: str) -> str:
        base = (req.base_url or self.default_base_url).rstrip("/")
        model = quote(req.model_name, safe="-._")
        return f"{base}/models/{model}:{method}"

    @staticmethod
    def _headers(req: ProviderRequest) -> dict[str, str]:
        if not req.api_key:
            raise ProviderError("Gemini credential is not configured")
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": req.api_key,
        }

    @staticmethod
    def _generation_config(req: ProviderRequest) -> dict[str, float | int]:
        return {
            "temperature": req.temperature,
            "maxOutputTokens": req.max_tokens,
        }

    async def chat(self, prompt: AssembledPrompt, req: ProviderRequest) -> Completion:
        body = self._contents(prompt)
        body["generationConfig"] = self._generation_config(req)
        headers = self._headers(req)
        async with httpx.AsyncClient(timeout=60, transport=self._transport) as client:
            try:
                response = await client.post(
                    self._url(req, "generateContent"),
                    headers=headers,
                    json=body,
                )
            except httpx.HTTPError:
                # Do not chain a transport exception: its text may contain request
                # metadata. The controlled error is safe for SSE/log formatting.
                raise ProviderError("Gemini request failed") from None
            self._raise_for_status(response)
            data = self._response_json(response)

        candidate = self._candidate(data)
        assert candidate is not None
        text = self._candidate_text(candidate)
        if not text:
            raise ProviderError("Gemini returned no usable text")
        usage = data.get("usageMetadata")
        usage = usage if isinstance(usage, dict) else {}
        token_count = usage.get("candidatesTokenCount", candidate.get("tokenCount", 0))
        if not isinstance(token_count, int) or isinstance(token_count, bool):
            token_count = 0
        finish_reason = candidate.get("finishReason")
        normalized_finish = (
            finish_reason.lower() if isinstance(finish_reason, str) else "stop"
        )
        return Completion(
            content=text,
            token_count=token_count,
            finish_reason=normalized_finish,
        )

    async def stream_chat(
        self, prompt: AssembledPrompt, req: ProviderRequest
    ) -> AsyncIterator[str]:
        body = self._contents(prompt)
        body["generationConfig"] = self._generation_config(req)
        headers = self._headers(req)
        yielded_text = False

        try:
            async with httpx.AsyncClient(timeout=None, transport=self._transport) as client:
                async with client.stream(
                    "POST",
                    self._url(req, "streamGenerateContent"),
                    params={"alt": "sse"},
                    headers=headers,
                    json=body,
                ) as response:
                    self._raise_for_status(response)
                    async for event in self._iter_sse_events(response):
                        candidate = self._candidate(event, allow_missing=True)
                        if candidate is None:
                            continue
                        text = self._candidate_text(candidate)
                        if text:
                            yielded_text = True
                            yield text
        except httpx.HTTPError:
            raise ProviderError("Gemini request failed") from None

        if not yielded_text:
            raise ProviderError("Gemini returned no usable text")

    @classmethod
    async def _iter_sse_events(
        cls, response: httpx.Response
    ) -> AsyncIterator[dict[str, Any]]:
        data_lines: list[str] = []

        def decode_pending() -> dict[str, Any] | None:
            if not data_lines:
                return None
            raw = "\n".join(data_lines)
            data_lines.clear()
            if raw == "[DONE]":
                return None
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                raise ProviderError("Gemini returned a malformed stream event") from None
            if not isinstance(event, dict):
                raise ProviderError("Gemini returned a malformed stream event")
            return event

        async for line in response.aiter_lines():
            if line == "":
                event = decode_pending()
                if event is not None:
                    yield event
                continue
            if line.startswith(":"):
                continue
            if line.startswith("data:"):
                data_lines.append(line[len("data:") :].lstrip())
                continue
            if line.startswith(("event:", "id:", "retry:")):
                continue
            raise ProviderError("Gemini returned an unexpected stream line")

        event = decode_pending()
        if event is not None:
            yield event

    @classmethod
    def _candidate(
        cls,
        data: dict[str, Any],
        *,
        allow_missing: bool = False,
    ) -> dict[str, Any] | None:
        prompt_feedback = data.get("promptFeedback")
        if isinstance(prompt_feedback, dict) and prompt_feedback.get("blockReason"):
            raise ProviderError("Gemini blocked the prompt")

        candidates = data.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            if allow_missing:
                return None
            raise ProviderError("Gemini returned no usable candidate")
        candidate = next(
            (
                item
                for item in candidates
                if isinstance(item, dict) and item.get("index") == 0
            ),
            candidates[0],
        )
        if not isinstance(candidate, dict):
            raise ProviderError("Gemini returned a malformed candidate")

        finish_reason = candidate.get("finishReason", "")
        if not isinstance(finish_reason, str):
            raise ProviderError("Gemini returned a malformed candidate")
        if finish_reason in _BLOCKED_FINISH_REASONS:
            raise ProviderError("Gemini blocked the response")
        if finish_reason not in _SUCCESS_FINISH_REASONS:
            raise ProviderError("Gemini could not complete the response")
        return candidate

    @staticmethod
    def _candidate_text(candidate: dict[str, Any]) -> str:
        content = candidate.get("content")
        if not isinstance(content, dict):
            return ""
        parts = content.get("parts")
        if not isinstance(parts, list):
            return ""
        return "".join(
            text
            for part in parts
            if isinstance(part, dict)
            and isinstance((text := part.get("text")), str)
            and text
        )

    @staticmethod
    def _response_json(response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except json.JSONDecodeError:
            raise ProviderError("Gemini returned a malformed response") from None
        if not isinstance(data, dict):
            raise ProviderError("Gemini returned a malformed response")
        return data

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        status = response.status_code
        if status == 429:
            details: dict[str, str] = {}
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                details["retry_after"] = retry_after
            raise ProviderRateLimited("Gemini rate limited", details)
        if status in {401, 403}:
            raise ProviderError("Gemini authentication or permission failed")
        if status == 404:
            raise ProviderError("Gemini model is unavailable")
        if status == 400:
            raise ProviderError("Gemini rejected the request")
        if status >= 500:
            raise ProviderError("Gemini provider unavailable")
        if status >= 400:
            raise ProviderError("Gemini request failed")
