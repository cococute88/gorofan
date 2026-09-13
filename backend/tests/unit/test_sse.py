"""Structured events are framed once by the installed SSE response library."""
import json

import pytest
from sse_starlette.event import ensure_bytes

from app.adapters.base import StreamEvent
from app.api.sse import format_sse, sse_stream


@pytest.mark.parametrize("event", [
    StreamEvent(event="token", delta="성공😊"),
    StreamEvent(event="done", token_count=3, finish_reason="stop"),
    StreamEvent(event="error", code="CONFLICT", message="stale anchor"),
])
@pytest.mark.parametrize("separator", ["\n", "\r\n"])
async def test_sse_response_encodes_structured_event_once(event: StreamEvent, separator: str) -> None:
    async def events():  # noqa: ANN202
        yield event

    items = [item async for item in sse_stream(events())]
    assert items == [format_sse(event)]
    wire = ensure_bytes(items[0], separator).decode("utf-8")
    assert wire.startswith(f"event: {event.event}{separator}data: ")
    assert wire.endswith(separator * 2)
    assert "data: event:" not in wire
    payload = json.loads(wire.split(separator)[1][6:])
    if event.event == "token":
        assert payload == {"delta": "성공😊"}
    elif event.event == "error":
        assert payload == {"code": "CONFLICT", "message": "stale anchor"}
    else:
        assert payload["finish_reason"] == "stop"
