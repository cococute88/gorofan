"""Authenticated Entry authoring, read/audit, and Review Card APIs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.errors import ValidationAppError
from app.core.pagination import PageParams
from app.models.user import User
from app.schemas.common import PageOut
from app.schemas.entry import (
    EntryAuthoringCreate,
    EntryRead,
    EntryReviewEdit,
    EntryReviewSupersedeRequest,
    EntryReviewSupersedeResponse,
    EntryScope,
    EntryStatus,
    EntrySubjectType,
    EntryType,
)
from app.services.entry_service import EntryService

router = APIRouter()
_entries = EntryService()


@router.get("/review", response_model=list[EntryRead])
async def list_review_entries(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _entries.list_review_entries(db, user.id)


@router.get("/review/{entry_id}", response_model=EntryRead)
async def get_review_entry(
    entry_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _entries.get_review_entry(db, user.id, entry_id)


@router.post("/review/{entry_id}/accept", response_model=EntryRead)
async def accept_review_entry(
    entry_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _entries.accept_review_entry(db, user.id, entry_id)


@router.post("/review/{entry_id}/reject", response_model=EntryRead)
async def reject_review_entry(
    entry_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _entries.reject_review_entry(db, user.id, entry_id)


@router.post("/review/{entry_id}/edit", response_model=EntryRead)
async def edit_review_entry(
    entry_id: str,
    dto: EntryReviewEdit,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _entries.edit_review_entry(db, user.id, entry_id, dto)


@router.post(
    "/review/{entry_id}/supersede", response_model=EntryReviewSupersedeResponse
)
async def supersede_review_entry(
    entry_id: str,
    dto: EntryReviewSupersedeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    old_entry, new_entry = await _entries.supersede(
        db,
        user.id,
        dto.current_entry_id,
        entry_id,
    )
    return EntryReviewSupersedeResponse(old_entry=old_entry, new_entry=new_entry)


@router.post("", response_model=EntryRead, status_code=status.HTTP_201_CREATED)
async def create_user_authored_entry(
    dto: EntryAuthoringCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Persist a deliberate human-authored canonical Entry.

    The DTO has no client-controlled status, owner, producer, or provenance.
    Existing canon corrections must name the Entry they supersede, preserving
    immutable history through the established lifecycle implementation.
    """
    return await _entries.create_user_authored(db, user.id, dto)


@router.get("", response_model=PageOut[EntryRead])
async def list_entries(
    scope_kind: EntryScope | None = Query(default=None, alias="scope"),
    scope_id: str | None = Query(default=None),
    entry_type: EntryType | None = Query(default=None, alias="type"),
    subject_type: EntrySubjectType | None = Query(default=None),
    subject_id: str | None = Query(default=None),
    subject_character_ids: list[str] = Query(default=[], alias="subject_character_id"),
    entry_status: EntryStatus | None = Query(default=None, alias="status"),
    include_history: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List canonical knowledge by default; audit/history requires opt-in."""
    if scope_kind is EntryScope.CHAT_PRIVATE:
        raise ValidationAppError("chat-private Memory is not persisted as an Entry")
    if scope_kind is EntryScope.USER and scope_id is not None:
        raise ValidationAppError("user scope cannot have scope_id")
    if scope_kind in {EntryScope.COLLECTION, EntryScope.WORK, EntryScope.CHARACTER, EntryScope.WORLD} and scope_id is None:
        raise ValidationAppError(f"{scope_kind.value} scope requires scope_id")
    if scope_id is not None and scope_kind is None:
        raise ValidationAppError("scope_id requires scope")
    if subject_type is None:
        if subject_id is not None or subject_character_ids:
            raise ValidationAppError("subject_id/subject_character_id require subject_type")
    elif subject_type is EntrySubjectType.CHARACTER_PAIR:
        if subject_id is not None:
            raise ValidationAppError("character-pair filter derives subject_id from subject_character_id")
        if len(subject_character_ids) != 2 or len(set(subject_character_ids)) != 2:
            raise ValidationAppError("character-pair filter requires two distinct subject_character_id")
        subject_id = "|".join(sorted(subject_character_ids))
    elif subject_id is None:
        raise ValidationAppError(f"{subject_type.value} filter requires subject_id")
    elif subject_character_ids:
        raise ValidationAppError("subject_character_id is only valid for character-pair filters")

    if entry_status is not None and entry_status is not EntryStatus.CANON and not include_history:
        raise ValidationAppError("Non-canon status filters require include_history=true")
    statuses = (
        [entry_status]
        if entry_status is not None
        else list(EntryStatus) if include_history else [EntryStatus.CANON]
    )
    page = await _entries.list_entries(
        db,
        user.id,
        page=PageParams(limit=limit, cursor=cursor),
        statuses=statuses,
        scope_kind=scope_kind,
        scope_id=scope_id,
        entry_type=entry_type,
        subject_type=subject_type,
        subject_id=subject_id,
        exclude_orphaned=not include_history,
    )
    return PageOut(items=page.items, next_cursor=page.next_cursor)


@router.get("/{entry_id}", response_model=EntryRead)
async def get_entry(
    entry_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Read one owned Entry, including its actual lifecycle status for audit."""
    return await _entries.get(db, user.id, entry_id)
