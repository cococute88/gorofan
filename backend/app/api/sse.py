"""SSE formatting helper (design 6.4)."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

from app.adapters.base import StreamEvent


def format_sse(evt: StreamEvent) -> str:
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
    return f"event: {evt.event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def sse_stream(events: AsyncIterator[StreamEvent]) -> AsyncIterator[str]:
    async for evt in events:
        yield format_sse(evt)
