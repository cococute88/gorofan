"""P1-7 edit-diff capture (docs/architecture/edit-diff-capture-design.md).

Capture writes the pair *(text the AI produced, text the human replaced it
with)* at the one moment both exist. It never creates, mutates, promotes, or
blocks an Entry, never enters retrieval or a prompt, and adds no HTTP surface.

Two rules govern everything here:

- **Full text, never a structured diff, never truncated.** Every other
  representation is derivable from the pair; the pair is derivable from none of
  them. A side over :data:`EDIT_DIFF_MAX_CHARS` is stored as ``oversize`` with
  NULL text and its hash and code-point length retained — a truncated pair
  looks complete and is wrong (design §11.2).
- **Text is byte-exact.** No Unicode normalization; consumers normalize at read
  time (design §8.4).

:data:`EDIT_DIFF_MAX_CHARS` is a code constant with **no schema dependency**.
No column, CHECK, or index refers to the number, so it can change without a
migration and rows written under an older value stay valid (design §11.1).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.models.edit_diff import EditDiffCapture
from app.repositories.edit_diff_repository import EditDiffCaptureRepository

EDIT_DIFF_MAX_CHARS = 100_000

SOURCE_KIND_ENTRY_REVIEW_EDIT = "entry-review-edit"
SOURCE_KIND_CHAPTER_CONTINUATION = "chapter-continuation"

PAYLOAD_STATE_STORED = "stored"
PAYLOAD_STATE_OVERSIZE = "oversize"

SETTLE_TRIGGER_NEXT_CONTINUATION = "next-continuation"

ENTRY_CONTEXT_KEYS = frozenset({"fields_changed"})
CHAPTER_CONTEXT_KEYS = frozenset(
    {
        "asset_id",
        "asset_version",
        "provider",
        "model",
        "insert_offset",
        "chapter_version",
        "partial_stream",
        "settle_trigger",
    }
)


@dataclass(frozen=True)
class CapturedSide:
    """One side of a capture, already reduced to what the row stores."""

    state: str
    text: str | None
    sha256: str
    chars: int


def measure_side(value: str) -> CapturedSide:
    """Reduce one text to its persisted form without ever truncating it."""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    chars = len(value)
    if chars > EDIT_DIFF_MAX_CHARS:
        return CapturedSide(
            state=PAYLOAD_STATE_OVERSIZE, text=None, sha256=digest, chars=chars
        )
    return CapturedSide(
        state=PAYLOAD_STATE_STORED, text=value, sha256=digest, chars=chars
    )


def _validated_context(
    context: dict[str, Any] | None, allowed: frozenset[str]
) -> dict[str, Any]:
    """Reject unknown keys — ``context`` is a closed set, not an extension point."""
    values = dict(context or {})
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"unsupported edit-diff context keys: {sorted(unknown)}")
    return values


class EditDiffCaptureService:
    """Writes capture rows inside the transaction that would destroy the pair."""

    def __init__(self) -> None:
        self.repo = EditDiffCaptureRepository()

    async def capture_entry_review_edit(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        entry_id: str,
        before_content: str,
        after_content: str,
        producer: str | None = None,
        fields_changed: list[str] | None = None,
    ) -> EditDiffCapture | None:
        """Capture a Review Card content replacement (Tier 1, atomic).

        Returns ``None`` when ``content`` did not actually change — a no-op diff
        is noise, and suppressing it also makes a duplicated request inert
        (design §6.2, §10). The caller must already hold the Entry row lock that
        ``EntryService._get_for_update()`` takes, which is what serializes the
        ``sequence`` derivation below.

        A Path A row is **born settled**: both sides exist at INSERT time.
        """
        before = measure_side(before_content)
        after = measure_side(after_content)
        if before.sha256 == after.sha256:
            return None

        sequence = await self.repo.next_sequence(
            session, user_id=user_id, entry_id=entry_id
        )
        capture = EditDiffCapture(
            user_id=user_id,
            source_kind=SOURCE_KIND_ENTRY_REVIEW_EDIT,
            entry_id=entry_id,
            chapter_id=None,
            sequence=sequence,
            before_state=before.state,
            after_state=after.state,
            before_text=before.text,
            after_text=after.text,
            before_sha256=before.sha256,
            after_sha256=after.sha256,
            before_chars=before.chars,
            after_chars=after.chars,
            producer=producer,
            context=_validated_context(
                {"fields_changed": sorted(fields_changed or [])}, ENTRY_CONTEXT_KEYS
            ),
            settled_at=utcnow(),
        )
        return await self.repo.add(session, capture)

    async def capture_chapter_continuation(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        chapter_id: str,
        segment_text: str,
        producer: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> EditDiffCapture:
        """Capture the AI segment before it loses its boundary (Tier 2, atomic).

        The row is written unsettled (``settled_at IS NULL``): the human side is
        resolved later, either by the next continuation's settle pass or — for
        the trailing segment of a chapter — at read time from the live
        ``chapters.content_text`` (design §6.3, §6.3.1).

        The caller must already hold the chapter row lock (design §10.1).
        """
        before = measure_side(segment_text)
        sequence = await self.repo.next_sequence(
            session, user_id=user_id, chapter_id=chapter_id
        )
        capture = EditDiffCapture(
            user_id=user_id,
            source_kind=SOURCE_KIND_CHAPTER_CONTINUATION,
            entry_id=None,
            chapter_id=chapter_id,
            sequence=sequence,
            before_state=before.state,
            after_state=None,
            before_text=before.text,
            after_text=None,
            before_sha256=before.sha256,
            after_sha256=None,
            before_chars=before.chars,
            after_chars=None,
            producer=producer,
            context=_validated_context(context, CHAPTER_CONTEXT_KEYS),
            settled_at=None,
        )
        return await self.repo.add(session, capture)

    async def settle_chapter_captures(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        chapter_id: str,
        after_text: str,
        trigger: str = SETTLE_TRIGGER_NEXT_CONTINUATION,
    ) -> list[str]:
        """Bracket this chapter's pending captures against the next segment.

        Guarded by ``settled_at IS NULL``, so a replayed settle affects zero
        rows and is not an error. Returns the ids actually settled. The caller
        must already hold the chapter row lock (design §10.1).
        """
        pending = await self.repo.list_unsettled_for_chapter(
            session, user_id=user_id, chapter_id=chapter_id
        )
        if not pending:
            return []

        after = measure_side(after_text)
        now = utcnow()
        settled: list[str] = []
        for capture in pending:
            capture.after_state = after.state
            capture.after_text = after.text
            capture.after_sha256 = after.sha256
            capture.after_chars = after.chars
            capture.settled_at = now
            capture.context = _validated_context(
                {**dict(capture.context or {}), "settle_trigger": trigger},
                CHAPTER_CONTEXT_KEYS,
            )
            settled.append(capture.id)
        await session.flush()
        return settled
