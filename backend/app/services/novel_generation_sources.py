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
    WorkCharacter association scan.  ``created_at, id`` makes that association
    insertion order explicit and reproducible without inventing a Character
    name/id product order.  The UUID is only a deterministic tie-break for an
    association timestamp collision.
    """

    characters = tuple(
        (
            await session.execute(
                select(Character)
                .join(WorkCharacter, WorkCharacter.character_id == Character.id)
                .where(
                    WorkCharacter.work_id == work.id,
                    Character.user_id == work.user_id,
                    Character.deleted_at.is_(None),
                )
                .order_by(WorkCharacter.created_at, WorkCharacter.id)
            )
        )
        .scalars()
        .all()
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
