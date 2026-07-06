"""Novel router incl. continue-writing SSE (design 6.2, 6.5, 11)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, status
from sse_starlette.sse import EventSourceResponse

from app.api.sse import sse_stream
from app.core.deps import get_current_user, get_state
from app.core.pagination import PageParams
from app.models.user import User
from app.schemas.common import PageOut
from app.schemas.novel import (
    ChapterCreate,
    ChapterOut,
    ChapterUpdate,
    ContinueRequest,
    ReorderRequest,
    WorkCharacterLink,
    WorkCharacterOut,
    WorkCreate,
    WorkOut,
    WorkUpdate,
)

router = APIRouter()


def _svc(state):  # noqa: ANN001
    return state.novel_service


@router.get("", response_model=PageOut[WorkOut])
async def list_works(limit: int = Query(default=20, le=100), user: User = Depends(get_current_user), state=Depends(get_state)):
    page = await _svc(state).list_works(user.id, PageParams(limit=limit))
    return PageOut(items=page.items, next_cursor=page.next_cursor)


@router.post("", response_model=WorkOut, status_code=status.HTTP_201_CREATED)
async def create_work(dto: WorkCreate, user: User = Depends(get_current_user), state=Depends(get_state)):
    return await _svc(state).create_work(user.id, dto)


@router.get("/{work_id}", response_model=WorkOut)
async def get_work(work_id: str, user: User = Depends(get_current_user), state=Depends(get_state)):
    return await _svc(state).get_work(user.id, work_id)


@router.patch("/{work_id}", response_model=WorkOut)
async def update_work(work_id: str, dto: WorkUpdate, user: User = Depends(get_current_user), state=Depends(get_state)):
    return await _svc(state).update_work(user.id, work_id, dto)


@router.delete("/{work_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work(work_id: str, user: User = Depends(get_current_user), state=Depends(get_state)):
    await _svc(state).delete_work(user.id, work_id)


@router.get("/{work_id}/chapters", response_model=list[ChapterOut])
async def list_chapters(work_id: str, user: User = Depends(get_current_user), state=Depends(get_state)):
    return await _svc(state).list_chapters(user.id, work_id)


@router.post("/{work_id}/chapters", response_model=ChapterOut, status_code=201)
async def create_chapter(work_id: str, dto: ChapterCreate, user: User = Depends(get_current_user), state=Depends(get_state)):
    return await _svc(state).create_chapter(user.id, work_id, dto)


@router.patch("/{work_id}/chapters:reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder(work_id: str, dto: ReorderRequest, user: User = Depends(get_current_user), state=Depends(get_state)):
    await _svc(state).reorder_chapters(user.id, work_id, dto.ordered_chapter_ids)


@router.get("/{work_id}/characters", response_model=list[WorkCharacterOut])
async def list_work_characters(work_id: str, user: User = Depends(get_current_user), state=Depends(get_state)):
    return await _svc(state).list_characters(user.id, work_id)


@router.post("/{work_id}/characters", response_model=WorkCharacterOut, status_code=201)
async def link_character(work_id: str, dto: WorkCharacterLink, user: User = Depends(get_current_user), state=Depends(get_state)):
    return await _svc(state).link_character(user.id, work_id, dto)


@router.delete("/{work_id}/characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_character(work_id: str, character_id: str, user: User = Depends(get_current_user), state=Depends(get_state)):
    await _svc(state).unlink_character(user.id, work_id, character_id)


# chapter-scoped (mounted under /works for path simplicity → /works/chapters/{id})
@router.patch("/chapters/{chapter_id}", response_model=ChapterOut)
async def update_chapter(chapter_id: str, dto: ChapterUpdate, user: User = Depends(get_current_user), state=Depends(get_state)):
    return await _svc(state).update_chapter(user.id, chapter_id, dto)


@router.delete("/chapters/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chapter(chapter_id: str, user: User = Depends(get_current_user), state=Depends(get_state)):
    await _svc(state).delete_chapter(user.id, chapter_id)


@router.post("/chapters/{chapter_id}/continue")
async def continue_chapter(
    chapter_id: str,
    dto: ContinueRequest,
    user: User = Depends(get_current_user),
    state=Depends(get_state),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    events = _svc(state).continue_chapter(user.id, chapter_id, dto)
    return EventSourceResponse(sse_stream(events))
