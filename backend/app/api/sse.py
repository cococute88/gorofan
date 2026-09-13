"""SSE formatting helper (design 6.4)."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

from app.adapters.base import StreamEvent


def format_sse(evt: StreamEvent) -> dict[str, str]:
    """Return structured input; EventSourceResponse alone owns wire framing."""
    data: dict[str, object]
    if evt.event == "token":
        data = {"delta": evt.delta}
    elif evt.event == "done":
        data = {
            "message_id": evt.message_id,
            "token_count": evt.token_count,
            "finish_reason": evt.finish_reason,
        }
    else:  # error
        data = {"code": evt.code, "message": evt.message}
    return {"event": evt.event, "data": json.dumps(data, ensure_ascii=False)}


async def sse_stream(events: AsyncIterator[StreamEvent]) -> AsyncIterator[dict[str, str]]:
    async for evt in events:
        yield format_sse(evt)
