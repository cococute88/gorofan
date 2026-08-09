"""Owner-scoped Chapter row locking seam.

`NovelService` historically loaded chapters with a plain ``session.get()``, and
the only serialization on the continuation path was ``_active_continue`` — a
module-level in-process set that does not survive multiple workers and is not a
database lock at all. Deriving ``MAX(sequence) + 1`` for an edit-diff capture
under that non-lock lets two concurrent continuations compute the same ordinal
and collide on ``uq_edit_diff_captures_chapter_sequence``, rolling back the
author's generated prose (edit-diff-capture-design §10.1).

This mirrors ``EntryRepository.get_for_update()``: PostgreSQL emits
``FOR UPDATE``; SQLite ignores the clause and keeps its single-writer behavior.
The statement builder is exposed separately so a test can assert on the
compiled statement — a SQLite-only assertion proves nothing here.
"""
from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.novel import Chapter


def chapter_for_update_stmt(chapter_id: str, *, user_id: str) -> Select[tuple[Chapter]]:
    """Build the owner-scoped locking SELECT for one chapter."""
    return (
        select(Chapter)
        .where(Chapter.id == chapter_id, Chapter.user_id == user_id)
        .with_for_update()
    )


class ChapterRepository:
    async def get_for_update(
        self, session: AsyncSession, chapter_id: str, *, user_id: str
    ) -> Chapter | None:
        """Lock one owner-scoped Chapter for a destructive append or settle."""
        stmt = chapter_for_update_stmt(chapter_id, user_id=user_id)
        return (await session.execute(stmt)).scalars().first()
