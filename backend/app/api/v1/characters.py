"""Character + Persona routers (design 6.2)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.pagination import PageParams
from app.models.user import User
from app.schemas.character import (
    CharacterCreate,
    CharacterOut,
    CharacterUpdate,
    PersonaCreate,
    PersonaOut,
    PersonaUpdate,
)
from app.schemas.common import PageOut
from app.services.character_service import CharacterService
from app.services.persona_service import PersonaService

router = APIRouter()
_chars = CharacterService()
_personas = PersonaService()


@router.get("", response_model=PageOut[CharacterOut])
async def list_characters(
    world_id: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    limit: int = Query(default=20, le=100),
    cursor: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    page = await _chars.list(
        db, user.id, PageParams(limit=limit, cursor=cursor), world_id=world_id, tag=tag
    )
    return PageOut(items=page.items, next_cursor=page.next_cursor)


@router.post("", response_model=CharacterOut, status_code=status.HTTP_201_CREATED)
async def create_character(
    dto: CharacterCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _chars.create(db, user.id, dto)


@router.get("/{character_id}", response_model=CharacterOut)
async def get_character(
    character_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _chars.get(db, user.id, character_id)


@router.patch("/{character_id}", response_model=CharacterOut)
async def update_character(
    character_id: str,
    dto: CharacterUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _chars.update(db, user.id, character_id, dto)


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(
    character_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _chars.soft_delete(db, user.id, character_id)


persona_router = APIRouter()


@persona_router.get("", response_model=PageOut[PersonaOut])
async def list_personas(
    limit: int = Query(default=20, le=100),
    cursor: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    page = await _personas.list(db, user.id, PageParams(limit=limit, cursor=cursor))
    return PageOut(items=page.items, next_cursor=page.next_cursor)


@persona_router.post("", response_model=PersonaOut, status_code=status.HTTP_201_CREATED)
async def create_persona(
    dto: PersonaCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _personas.create(db, user.id, dto)


@persona_router.get("/{persona_id}", response_model=PersonaOut)
async def get_persona(
    persona_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _personas.get(db, user.id, persona_id)


@persona_router.patch("/{persona_id}", response_model=PersonaOut)
async def update_persona(
    persona_id: str,
    dto: PersonaUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _personas.update(db, user.id, persona_id, dto)


@persona_router.delete("/{persona_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_persona(
    persona_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _personas.delete(db, user.id, persona_id)
