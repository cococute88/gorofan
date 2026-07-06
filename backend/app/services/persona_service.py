"""PersonaService (design 8.2)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.core.pagination import Page, PageParams
from app.models.character import Persona
from app.repositories.base import BaseRepository
from app.schemas.character import PersonaCreate, PersonaUpdate


class PersonaService:
    def __init__(self) -> None:
        self.repo = BaseRepository(Persona)

    async def create(self, session: AsyncSession, user_id: str, dto: PersonaCreate) -> Persona:
        p = Persona(user_id=user_id, **dto.model_dump())
        await self.repo.add(session, p)
        await session.commit()
        await session.refresh(p)
        return p

    async def list(self, session: AsyncSession, user_id: str, page: PageParams) -> Page[Persona]:
        return await self.repo.list_page(session, user_id=user_id, page=page)

    async def get(self, session: AsyncSession, user_id: str, persona_id: str) -> Persona:
        p = await self.repo.get(session, persona_id, user_id=user_id)
        if p is None:
            raise NotFound("Persona not found")
        return p

    async def update(
        self, session: AsyncSession, user_id: str, persona_id: str, dto: PersonaUpdate
    ) -> Persona:
        p = await self.get(session, user_id, persona_id)
        await self.repo.update(session, p, dto.model_dump(exclude_unset=True))
        await session.commit()
        await session.refresh(p)
        return p

    async def delete(self, session: AsyncSession, user_id: str, persona_id: str) -> None:
        p = await self.get(session, user_id, persona_id)
        await session.delete(p)
        await session.commit()
