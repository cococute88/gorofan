"""World / Lore / Glossary router (design 6.2)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.pagination import PageParams
from app.models.user import User
from app.schemas.common import PageOut
from app.schemas.world import (
    GlossaryCreate,
    GlossaryOut,
    LorebookCreate,
    LorebookOut,
    LoreEntryCreate,
    LoreEntryOut,
    WorldCreate,
    WorldOut,
    WorldUpdate,
)
from app.services.world_service import WorldService

router = APIRouter()
_svc = WorldService()


@router.get("", response_model=PageOut[WorldOut])
async def list_worlds(
    limit: int = Query(default=20, le=100),
    cursor: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    page = await _svc.list(db, user.id, PageParams(limit=limit, cursor=cursor))
    return PageOut(items=page.items, next_cursor=page.next_cursor)


@router.post("", response_model=WorldOut, status_code=status.HTTP_201_CREATED)
async def create_world(dto: WorldCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _svc.create(db, user.id, dto)


@router.get("/{world_id}", response_model=WorldOut)
async def get_world(world_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _svc.get(db, user.id, world_id)


@router.patch("/{world_id}", response_model=WorldOut)
async def update_world(world_id: str, dto: WorldUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _svc.update(db, user.id, world_id, dto)


@router.delete("/{world_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_world(world_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _svc.soft_delete(db, user.id, world_id)


# ----- lorebooks -----
@router.get("/{world_id}/lorebooks", response_model=list[LorebookOut])
async def list_lorebooks(world_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _svc.list_lorebooks(db, user.id, world_id)


@router.post("/{world_id}/lorebooks", response_model=LorebookOut, status_code=201)
async def add_lorebook(world_id: str, dto: LorebookCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _svc.add_lorebook(db, user.id, world_id, dto)


@router.get("/lorebooks/{lorebook_id}/entries", response_model=list[LoreEntryOut])
async def list_entries(lorebook_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _svc.list_lore_entries(db, user.id, lorebook_id)


@router.post("/lorebooks/{lorebook_id}/entries", response_model=LoreEntryOut, status_code=201)
async def add_entry(lorebook_id: str, dto: LoreEntryCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _svc.add_lore_entry(db, user.id, lorebook_id, dto)


# ----- glossary -----
@router.get("/{world_id}/glossary", response_model=list[GlossaryOut])
async def list_glossary(world_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _svc.list_glossary(db, user.id, world_id)


@router.post("/{world_id}/glossary", response_model=GlossaryOut, status_code=201)
async def add_glossary(world_id: str, dto: GlossaryCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await _svc.add_glossary_term(db, user.id, world_id, dto)
