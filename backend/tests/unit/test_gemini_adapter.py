"""Gemini REST adapter contract and secret-safety tests for AOS-3."""
from __future__ import annotations

import asyncio
import json
import logging

import httpx
import pytest

from app.adapters.base import AssembledPrompt, ChatMessage, ProviderRequest
from app.adapters.gemini import GeminiAdapter
from app.core.errors import ProviderError, ProviderRateLimited
from app.core.logging import JsonFormatter

SECRET = "gemini-secret-never-expose"


def _prompt() -> AssembledPrompt:
    return AssembledPrompt(
        system="시스템 권한",
        messages=[
            ChatMessage(role="system", content="시스템 권한"),
            ChatMessage(role="user", content="첫 질문"),
            ChatMessage(role="assistant", content="첫 응답"),
            ChatMessage(role="user", content="현재 집필 요청"),
        ],
    )


def _request(*, api_key: str | None = SECRET) -> ProviderRequest:
    return ProviderRequest(
        provider="gemini",
        model_name="gemini-3.8-flash",
        base_url=None,
        api_key=api_key,
        temperature=0.65,
        max_tokens=321,
        context_window=1_048_576,
    )


def _sse(*events: dict) -> str:
    return "".join(
        f"data: {json.dumps(event, ensure_ascii=False)}\n\n" for event in events
    )


def _response_event(
    *texts: str,
    finish_reason: str | None = None,
    index: int = 0,
) -> dict:
    candidate: dict = {
        "index": index,
        "content": {"role": "model", "parts": [{"text": text} for text in texts]},
    }
    if finish_reason is not None:
        candidate["finishReason"] = finish_reason
    return {"candidates": [candidate]}


async def _collect(adapter: GeminiAdapter, req: ProviderRequest | None = None) -> list[str]:
    return [token async for token in adapter.stream_chat(_prompt(), req or _request())]


@pytest.mark.asyncio
async def test_gemini_stream_maps_system_turn_order_config_and_header_without_query_key() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            text=_sse(_response_event("완료", finish_reason="STOP")),
            headers={"Content-Type": "text/event-stream; charset=utf-8"},
        )

    tokens = await _collect(GeminiAdapter(transport=httpx.MockTransport(handler)))

    assert tokens == ["완료"]
    assert len(captured) == 1
    request = captured[0]
    assert request.headers["x-goog-api-key"] == SECRET
    assert SECRET not in str(request.url)
    assert request.url.params.get("key") is None
    assert request.url.params["alt"] == "sse"
    body = json.loads(request.content)
    assert body["systemInstruction"] == {"parts": [{"text": "시스템 권한"}]}
    assert body["contents"] == [
        {"role": "user", "parts": [{"text": "첫 질문"}]},
        {"role": "model", "parts": [{"text": "첫 응답"}]},
        {"role": "user", "parts": [{"text": "현재 집필 요청"}]},
    ]
    assert body["generationConfig"] == {
        "temperature": 0.65,
        "maxOutputTokens": 321,
    }
    assert json.dumps(body, ensure_ascii=False).count("시스템 권한") == 1


@pytest.mark.asyncio
async def test_gemini_stream_handles_multiple_parts_events_comments_and_unicode() -> None:
    stream = (
        ": keepalive\n\n"
        "event: message\n"
        + _sse(_response_event("한글", "\n日本語"))
        + "id: final\n"
        + _sse(_response_event(" 😊 “끝”", finish_reason="STOP"))
        + "data: [DONE]\n\n"
    )
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            content=stream.encode("utf-8"),
            headers={"Content-Type": "text/event-stream; charset=utf-8"},
        )
    )

    assert await _collect(GeminiAdapter(transport=transport)) == [
        "한글\n日本語",
        " 😊 “끝”",
    ]


@pytest.mark.asyncio
async def test_gemini_stream_uses_only_primary_candidate_and_all_its_text_parts() -> None:
    event = {
        "candidates": [
            {
                "index": 1,
                "content": {"parts": [{"text": "대안은 제외"}]},
                "finishReason": "STOP",
            },
            {
                "index": 0,
                "content": {"parts": [{"text": "첫째"}, {"text": "둘째"}]},
                "finishReason": "STOP",
            },
        ]
    }
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, text=_sse(event))
    )

    assert await _collect(GeminiAdapter(transport=transport)) == ["첫째둘째"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "error_type", "message"),
    [
        (400, ProviderError, "Gemini rejected the request"),
        (401, ProviderError, "Gemini authentication or permission failed"),
        (403, ProviderError, "Gemini authentication or permission failed"),
        (404, ProviderError, "Gemini model is unavailable"),
        (429, ProviderRateLimited, "Gemini rate limited"),
        (500, ProviderError, "Gemini provider unavailable"),
        (503, ProviderError, "Gemini provider unavailable"),
    ],
)
async def test_gemini_http_errors_are_controlled(
    status: int, error_type: type[ProviderError], message: str
) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            status,
            json={"error": {"message": f"raw response {SECRET}"}},
        )
    )

    with pytest.raises(error_type, match=message) as raised:
        await _collect(GeminiAdapter(transport=transport))

    assert SECRET not in str(raised.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event",
    [
        {"promptFeedback": {"blockReason": "PROHIBITED_CONTENT"}},
        _response_event(finish_reason="SAFETY"),
        _response_event(finish_reason="BLOCKLIST"),
        _response_event(finish_reason="PROHIBITED_CONTENT"),
    ],
)
async def test_gemini_blocked_responses_are_failures(event: dict) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, text=_sse(event))
    )

    with pytest.raises(ProviderError, match="Gemini blocked"):
        await _collect(GeminiAdapter(transport=transport))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        _sse({"usageMetadata": {"totalTokenCount": 12}}),
        _sse(_response_event("", finish_reason="STOP")),
        ": keepalive\n\n",
    ],
)
async def test_gemini_empty_stream_is_not_success(body: str) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, text=body)
    )

    with pytest.raises(ProviderError, match="no usable text"):
        await _collect(GeminiAdapter(transport=transport))


@pytest.mark.asyncio
@pytest.mark.parametrize("body", ["data: {bad json}\n\n", "unexpected\n\n"])
async def test_gemini_malformed_stream_is_controlled(body: str) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, text=body)
    )

    with pytest.raises(ProviderError, match="malformed|unexpected"):
        await _collect(GeminiAdapter(transport=transport))


@pytest.mark.asyncio
async def test_gemini_missing_credential_fails_before_transport() -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, text=_sse(_response_event("금지")))

    with pytest.raises(ProviderError, match="credential is not configured"):
        await _collect(
            GeminiAdapter(transport=httpx.MockTransport(handler)),
            _request(api_key=None),
        )

    assert attempts == 0


@pytest.mark.asyncio
async def test_gemini_transport_exception_cannot_leak_secret_in_error_or_log() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"transport detail {SECRET}", request=request)

    try:
        await _collect(GeminiAdapter(transport=httpx.MockTransport(handler)))
    except ProviderError as exc:
        assert SECRET not in str(exc)
        record = logging.LogRecord(
            "provider",
            logging.ERROR,
            __file__,
            1,
            "gemini.failed",
            (),
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        assert SECRET not in JsonFormatter().format(record)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("ProviderError was not raised")


@pytest.mark.asyncio
async def test_gemini_non_streaming_maps_completion_and_rejects_empty() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                200,
                json={
                    **_response_event("완성", finish_reason="MAX_TOKENS"),
                    "usageMetadata": {"candidatesTokenCount": 7},
                },
            )
        return httpx.Response(200, json=_response_event("", finish_reason="STOP"))

    adapter = GeminiAdapter(transport=httpx.MockTransport(handler))
    completion = await adapter.chat(_prompt(), _request())

    assert completion.content == "완성"
    assert completion.token_count == 7
    assert completion.finish_reason == "max_tokens"
    with pytest.raises(ProviderError, match="no usable text"):
        await adapter.chat(_prompt(), _request())


def test_gemini_capability_authority_and_unknown_fallback() -> None:
    adapter = GeminiAdapter()

    known_models = (
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.5-pro",
    )
    unknown = adapter.capabilities("gemini-future-flash")

    for model in known_models:
        capability = adapter.capabilities(model)
        assert capability.context_window == 1_048_576
        assert capability.max_output_tokens == 65_536
        assert capability.supports_streaming is True
    assert unknown.context_window == 32_768
    assert unknown.max_output_tokens == 8_192
    assert unknown.context_window < adapter.capabilities(known_models[0]).context_window


class _BlockingSSEStream(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.closed = False
        self.waiting = asyncio.Event()

    async def __aiter__(self):  # noqa: ANN202
        yield _sse(_response_event("첫 토큰")).encode("utf-8")
        self.waiting.set()
        await asyncio.Event().wait()

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_gemini_stream_cancellation_closes_upstream_without_duplicate_request() -> None:
    upstream = _BlockingSSEStream()
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, stream=upstream)

    stream = GeminiAdapter(
        transport=httpx.MockTransport(handler)
    ).stream_chat(_prompt(), _request())
    assert await anext(stream) == "첫 토큰"

    async def next_token() -> str:
        return await anext(stream)

    pending: asyncio.Task[str] = asyncio.create_task(next_token())
    await upstream.waiting.wait()
    pending.cancel()

    with pytest.raises(asyncio.CancelledError):
        await pending

    assert pending.done()
    assert upstream.closed is True
    assert attempts == 1
