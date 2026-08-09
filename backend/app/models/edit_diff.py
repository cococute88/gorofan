"""Edit-diff capture persistence (P1-7).

An edit-diff capture is a **non-Entry operational learning-source record**: it
asserts nothing, carries no scope, never enters retrieval or a prompt, and has
no canon lifecycle. It exists only so the pair *(what the AI wrote, what the
human replaced it with)* survives the write that would otherwise destroy it
(ADR-010 §2.2, RFC-001 §8.8).

Contract source: ``docs/architecture/edit-diff-capture-design.md`` §8.

Two invariants are easy to break and deliberately encoded here:

- ``before_state`` and ``after_state`` are **independent** retention facts.
  "Pending" is not a state value — it is ``settled_at IS NULL`` (§6.3.1), so an
  oversize *and* not-yet-settled chapter row is representable.
- **No ORM relationship points at this table.** Deletion cascades are enforced
  by the database ``ON DELETE CASCADE``. A relationship without
  ``passive_deletes=True`` would null ``chapter_id`` and silently orphan the
  author's captured prose (§12).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel
from app.db.types import JSONDict

EDIT_DIFF_SOURCE_KIND_VALUES = ("entry-review-edit", "chapter-continuation")
EDIT_DIFF_PAYLOAD_STATE_VALUES = ("stored", "oversize")


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class EditDiffCapture(BaseModel):
    """One captured (before, after) text pair anchored to exactly one source."""

    __tablename__ = "edit_diff_captures"
    __table_args__ = (
        CheckConstraint(
            f"source_kind IN ({_quoted(EDIT_DIFF_SOURCE_KIND_VALUES)})",
            name="ck_edit_diff_captures_source_kind",
        ),
        CheckConstraint(
            f"before_state IN ({_quoted(EDIT_DIFF_PAYLOAD_STATE_VALUES)})",
            name="ck_edit_diff_captures_before_state",
        ),
        CheckConstraint(
            f"after_state IS NULL OR after_state IN ({_quoted(EDIT_DIFF_PAYLOAD_STATE_VALUES)})",
            name="ck_edit_diff_captures_after_state",
        ),
        CheckConstraint(
            "(entry_id IS NOT NULL AND chapter_id IS NULL)"
            " OR (entry_id IS NULL AND chapter_id IS NOT NULL)",
            name="ck_edit_diff_captures_one_source",
        ),
        CheckConstraint("sequence >= 0", name="ck_edit_diff_captures_sequence"),
        CheckConstraint("before_chars >= 0", name="ck_edit_diff_captures_before_chars"),
        CheckConstraint(
            "after_chars IS NULL OR after_chars >= 0",
            name="ck_edit_diff_captures_after_chars",
        ),
        CheckConstraint(
            "(before_state = 'stored' AND before_text IS NOT NULL)"
            " OR (before_state = 'oversize' AND before_text IS NULL)",
            name="ck_edit_diff_captures_before_payload",
        ),
        CheckConstraint(
            "after_state IS NULL"
            " OR (after_state = 'stored' AND after_text IS NOT NULL)"
            " OR (after_state = 'oversize' AND after_text IS NULL)",
            name="ck_edit_diff_captures_after_payload",
        ),
        CheckConstraint(
            "(settled_at IS NULL"
            " AND after_state IS NULL AND after_sha256 IS NULL AND after_chars IS NULL)"
            " OR (settled_at IS NOT NULL"
            " AND after_state IS NOT NULL AND after_sha256 IS NOT NULL"
            " AND after_chars IS NOT NULL)",
            name="ck_edit_diff_captures_settled",
        ),
        CheckConstraint(
            "source_kind <> 'entry-review-edit' OR settled_at IS NOT NULL",
            name="ck_edit_diff_captures_entry_settled",
        ),
        UniqueConstraint(
            "entry_id", "sequence", name="uq_edit_diff_captures_entry_sequence"
        ),
        UniqueConstraint(
            "chapter_id", "sequence", name="uq_edit_diff_captures_chapter_sequence"
        ),
        Index("ix_edit_diff_captures_owner_created", "user_id", "created_at"),
        Index(
            "ix_edit_diff_captures_owner_kind_settled",
            "user_id",
            "source_kind",
            "settled_at",
        ),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    source_kind: Mapped[str] = mapped_column(String(32))
    entry_id: Mapped[str | None] = mapped_column(
        ForeignKey("entries.id", ondelete="CASCADE"), nullable=True
    )
    chapter_id: Mapped[str | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), nullable=True
    )
    sequence: Mapped[int] = mapped_column(Integer)

    before_state: Mapped[str] = mapped_column(String(16))
    after_state: Mapped[str | None] = mapped_column(String(16), nullable=True)
    before_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    before_sha256: Mapped[str] = mapped_column(String(64))
    after_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    before_chars: Mapped[int] = mapped_column(Integer)
    after_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)

    producer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    context: Mapped[dict] = mapped_column(JSONDict, default=dict)
    settled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
