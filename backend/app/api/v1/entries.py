"""Authenticated Entry Review Card API."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.entry import EntryRead, EntryReviewEdit
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
