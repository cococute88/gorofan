"""Owner-scoped persistence access for P1-7 edit-diff captures.

Every method is owner-scoped (ADR-017 §2.3). Nothing here reads across users,
and no method returns captured text to a caller that did not already hold it.
"""
from __future__ import annotations

import builtins

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.edit_diff import EditDiffCapture


class EditDiffCaptureRepository:
    async def add(
        self, session: AsyncSession, capture: EditDiffCapture
    ) -> EditDiffCapture:
        session.add(capture)
        await session.flush()
        return capture

    async def next_sequence(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        entry_id: str | None = None,
        chapter_id: str | None = None,
    ) -> int:
        """Return ``MAX(sequence) + 1`` for one source, or 0.

        The caller **must** already hold a row lock on that source. Without it
        two writers can read the same maximum and collide on the per-source
        unique constraint (design §10.1).
        """
        stmt = select(func.max(EditDiffCapture.sequence)).where(
            EditDiffCapture.user_id == user_id
        )
        if entry_id is not None:
            stmt = stmt.where(EditDiffCapture.entry_id == entry_id)
        elif chapter_id is not None:
            stmt = stmt.where(EditDiffCapture.chapter_id == chapter_id)
        else:  # pragma: no cover - guarded by the service layer
            raise ValueError("next_sequence requires entry_id or chapter_id")
        current = (await session.execute(stmt)).scalar_one_or_none()
        return 0 if current is None else int(current) + 1

    async def list_unsettled_for_chapter(
        self, session: AsyncSession, *, user_id: str, chapter_id: str
    ) -> builtins.list[EditDiffCapture]:
        """Return this chapter's not-yet-settled captures, oldest first.

        ``settled_at IS NULL`` is how "pending" is expressed; it is a valid
        terminal state for the trailing segment of a chapter (design §6.3.1),
        not an error condition.
        """
        stmt = (
            select(EditDiffCapture)
            .where(
                EditDiffCapture.user_id == user_id,
                EditDiffCapture.chapter_id == chapter_id,
                EditDiffCapture.settled_at.is_(None),
            )
            .order_by(EditDiffCapture.sequence)
        )
        return list((await session.execute(stmt)).scalars().all())
