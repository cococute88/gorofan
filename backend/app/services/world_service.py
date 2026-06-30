"""WorldService (design 8.2). World/Lorebook/LoreEntry/Glossary management."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.core.pagination import Page, PageParams
from app.models.world import GlossaryTerm, Lorebook, LoreEntry, World
from app.repositories.base import BaseRepository
from app.schemas.world import (
    GlossaryCreate,
    LorebookCreate,
    LoreEntryCreate,
    WorldCreate,
    WorldUpdate,
)


class WorldService:
    def __init__(self) -> None:
        self.repo = BaseRepository(World)

    async def create(self, session: AsyncSession, user_id: str, dto: WorldCreate) -> World:
        world = World(user_id=user_id, **dto.model_dump())
        await self.repo.add(session, world)
        await session.commit()
        await session.refresh(world)
        return world

    async def get(self, session: AsyncSession, user_id: str, world_id: str) -> World:
        world = await self.repo.get(session, world_id, user_id=user_id)
        if world is None:
            raise NotFound("World not found", {"id": world_id})
        return world

    async def list(self, session, user_id, page: PageParams) -> Page[World]:  # noqa: ANN001
        return await self.repo.list_page(session, user_id=user_id, page=page)

    async def update(self, session, user_id, world_id, dto: WorldUpdate) -> World:  # noqa: ANN001
        world = await self.get(session, user_id, world_id)
        await self.repo.update(session, world, dto.model_dump(exclude_unset=True))
        await session.commit()
        await session.refresh(world)
        return world

    async def soft_delete(self, session, user_id, world_id) -> None:  # noqa: ANN001
        world = await self.get(session, user_id, world_id)
        # detach linked characters/works world_id is handled by ON DELETE SET NULL on hard delete;
        # for soft delete we leave links and rely on _active filtering of the world (design 4.7).
        await self.repo.soft_delete(session, world)
        await session.commit()

    # ----- lorebooks / entries / glossary -----
    async def add_lorebook(self, session, user_id, world_id, dto: LorebookCreate) -> Lorebook:  # noqa: ANN001
        await self.get(session, user_id, world_id)
        lb = Lorebook(world_id=world_id, **dto.model_dump())
        session.add(lb)
        await session.commit()
        await session.refresh(lb)
        return lb

    async def list_lorebooks(self, session, user_id, world_id) -> list[Lorebook]:  # noqa: ANN001
        await self.get(session, user_id, world_id)
        stmt = select(Lorebook).where(Lorebook.world_id == world_id)
        return list((await session.execute(stmt)).scalars().all())

    async def add_lore_entry(self, session, user_id, lorebook_id, dto: LoreEntryCreate) -> LoreEntry:  # noqa: ANN001
        lb = await session.get(Lorebook, lorebook_id)
        if lb is None:
            raise NotFound("Lorebook not found")
        await self.get(session, user_id, lb.world_id)  # ownership via parent world
        entry = LoreEntry(lorebook_id=lorebook_id, **dto.model_dump())
        session.add(entry)
        await session.commit()
        await session.refresh(entry)
        return entry

    async def list_lore_entries(self, session, user_id, lorebook_id) -> list[LoreEntry]:  # noqa: ANN001
        lb = await session.get(Lorebook, lorebook_id)
        if lb is None:
            raise NotFound("Lorebook not found")
        await self.get(session, user_id, lb.world_id)
        stmt = select(LoreEntry).where(LoreEntry.lorebook_id == lorebook_id)
        return list((await session.execute(stmt)).scalars().all())

    async def add_glossary_term(self, session, user_id, world_id, dto: GlossaryCreate) -> GlossaryTerm:  # noqa: ANN001
        await self.get(session, user_id, world_id)
        term = GlossaryTerm(world_id=world_id, **dto.model_dump())
        session.add(term)
        await session.commit()
        await session.refresh(term)
        return term

    async def list_glossary(self, session, user_id, world_id) -> list[GlossaryTerm]:  # noqa: ANN001
        await self.get(session, user_id, world_id)
        stmt = select(GlossaryTerm).where(GlossaryTerm.world_id == world_id)
        return list((await session.execute(stmt)).scalars().all())
