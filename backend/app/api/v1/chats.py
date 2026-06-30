"""Chat router incl. SSE streaming (design 6.2, 6.4, 6.5)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, status
from sse_starlette.sse import EventSourceResponse

from app.api.sse import sse_stream
from app.core.deps import get_current_user, get_state
from app.core.pagination import PageParams
from app.models.user import User
from app.schemas.chat import ChatCreate, ChatOut, MessageCreate, MessageOut
from app.schemas.common import PageOut

router = APIRouter()


def _service(state):  # noqa: ANN001
    return state.chat_service


@router.get("", response_model=PageOut[ChatOut])
async def list_chats(
    limit: int = Query(default=20, le=100),
    user: User = Depends(get_current_user),
    state=Depends(get_state),
):
    page = await _service(state).list_sessions(user.id, PageParams(limit=limit))
    return PageOut(items=page.items, next_cursor=page.next_cursor)


@router.post("", response_model=ChatOut, status_code=status.HTTP_201_CREATED)
async def create_chat(dto: ChatCreate, user: User = Depends(get_current_user), state=Depends(get_state)):
    return await _service(state).create_session(user.id, dto)


@router.get("/{chat_id}/messages", response_model=PageOut[MessageOut])
async def list_messages(
    chat_id: str,
    limit: int = Query(default=30, le=100),
    before: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    state=Depends(get_state),
):
    page = await _service(state).get_messages(
        user.id, chat_id, PageParams(limit=limit, before=before)
    )
    return PageOut(items=page.items, next_cursor=page.next_cursor)


@router.post("/{chat_id}/messages")
async def send_message(
    chat_id: str,
    dto: MessageCreate,
    user: User = Depends(get_current_user),
    state=Depends(get_state),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    events = _service(state).stream_message(user.id, chat_id, dto)
    return EventSourceResponse(sse_stream(events))


@router.post("/{chat_id}/regenerate")
async def regenerate(chat_id: str, user: User = Depends(get_current_user), state=Depends(get_state)):
    events = _service(state).regenerate(user.id, chat_id)
    return EventSourceResponse(sse_stream(events))


@router.post("/{chat_id}/summarize", status_code=status.HTTP_202_ACCEPTED)
async def summarize(chat_id: str, user: User = Depends(get_current_user), state=Depends(get_state)):
    await _service(state).force_summarize(user.id, chat_id)
    return {"status": "queued"}
