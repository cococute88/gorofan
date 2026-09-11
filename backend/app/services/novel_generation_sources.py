"""Shared read-only source selection for Novel generation and its P1-8 shadow."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.character import Character
from app.models.novel import Work, WorkCharacter
from app.models.world import World


@dataclass(frozen=True)
class NovelGenerationSources:
    """Owner-safe legacy sources in the established association order."""

    characters: tuple[Character, ...]
    world: World | None


async def load_novel_generation_sources(
    session: AsyncSession, work: Work
) -> NovelGenerationSources:
    """Load the Character/World sources shared by production and P1-8.

    Before AOS-1 the production query preserved the order returned by the
    WorkCharacter association scan.  The domain has no canonical equal-key
    ordering column, so compatibility requires snapshotting that supplied
    sequence without introducing a Character id/name/UUID tie-break.
    """

    links = tuple(
        (
            await session.execute(
                select(WorkCharacter).where(WorkCharacter.work_id == work.id)
            )
        ).scalars().all()
    )
    character_ids = tuple(link.character_id for link in links)
    characters_by_id: dict[str, Character] = {}
    if character_ids:
        characters_by_id = {
            character.id: character
            for character in (
                (
                    await session.execute(
                        select(Character).where(
                            Character.id.in_(character_ids),
                            Character.user_id == work.user_id,
                            Character.deleted_at.is_(None),
                        )
                    )
                )
                .scalars()
                .all()
            )
        }
    characters = tuple(
        characters_by_id[link.character_id]
        for link in links
        if link.character_id in characters_by_id
    )
    world = None
    if work.world_id:
        world = (
            await session.execute(
                select(World).where(
                    World.id == work.world_id,
                    World.user_id == work.user_id,
                    World.deleted_at.is_(None),
                )
            )
        ).scalars().first()
    return NovelGenerationSources(characters=characters, world=world)
