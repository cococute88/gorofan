"""CharacterService (design 8.2). Enforces INV-2 (world ownership / Property 2)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound, ValidationAppError
from app.core.pagination import Page, PageParams
from app.models.character import Character
from app.models.world import World
from app.repositories.base import BaseRepository
from app.schemas.character import CharacterCreate, CharacterUpdate


class CharacterService:
    def __init__(self) -> None:
        self.repo = BaseRepository(Character)

    async def create(self, session: AsyncSession, user_id: str, dto: CharacterCreate) -> Character:
        if dto.world_id:
            await self._assert_world_owned(session, user_id, dto.world_id)
        ch = Character(user_id=user_id, **dto.model_dump())
        await self.repo.add(session, ch)
        await session.commit()
        await session.refresh(ch)
        return ch

    async def get(self, session: AsyncSession, user_id: str, character_id: str) -> Character:
        ch = await self.repo.get(session, character_id, user_id=user_id)
        if ch is None:
            raise NotFound("Character not found", {"id": character_id})
        return ch

    async def list(
        self, session: AsyncSession, user_id: str, page: PageParams, *, world_id=None, tag=None
    ) -> Page[Character]:
        def extra(stmt):
            if world_id:
                stmt = stmt.where(Character.world_id == world_id)
            return stmt

        return await self.repo.list_page(session, user_id=user_id, page=page, extra=extra)

    async def update(
        self, session: AsyncSession, user_id: str, character_id: str, dto: CharacterUpdate
    ) -> Character:
        ch = await self.get(session, user_id, character_id)
        if dto.world_id:
            await self._assert_world_owned(session, user_id, dto.world_id)
        await self.repo.update(session, ch, dto.model_dump(exclude_unset=True))
        await session.commit()
        await session.refresh(ch)
        return ch

    async def soft_delete(self, session: AsyncSession, user_id: str, character_id: str) -> None:
        ch = await self.get(session, user_id, character_id)
        await self.repo.soft_delete(session, ch)
        await session.commit()

    async def _assert_world_owned(self, session, user_id, world_id) -> None:  # noqa: ANN001
        world = await session.get(World, world_id)
        if world is None or world.user_id != user_id or world.deleted_at is not None:
            raise ValidationAppError("world_id must reference your own world", {"inv": "INV-2"})
