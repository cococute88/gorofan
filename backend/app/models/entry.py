"""Entry Store persistence model (RFC-002).

Entries add a unified creative-knowledge shape without replacing legacy
aggregate tables. Aggregate references remain bounded, owner-validated
application references rather than unsafe polymorphic foreign keys.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel
from app.db.types import JSONDict

ENTRY_SCOPE_VALUES = ("user", "collection", "work", "character", "world")
ENTRY_TYPE_VALUES = (
    "character.identity",
    "character.behavior",
    "character.voice",
    "character.exemplar",
    "world.fact",
    "world.term",
    "story.fact",
    "story.knowledge",
    "story.promise",
    "story.summary",
    "relationship.state",
    "style.preference",
    "user.preference",
    "note",
)
ENTRY_STATUS_VALUES = ("captured", "proposed", "canon", "rejected", "superseded")


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class Entry(BaseModel):
    """One owned, scoped, prose-first unit of creative knowledge."""

    __tablename__ = "entries"
    __table_args__ = (
        CheckConstraint(
            f"scope_kind IN ({_quoted(ENTRY_SCOPE_VALUES)})",
            name="ck_entries_scope_kind",
        ),
        CheckConstraint(
            f"type IN ({_quoted(ENTRY_TYPE_VALUES)})",
            name="ck_entries_type",
        ),
        CheckConstraint(
            f"status IN ({_quoted(ENTRY_STATUS_VALUES)})",
            name="ck_entries_status",
        ),
        CheckConstraint("length(trim(content)) > 0", name="ck_entries_content_nonempty"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="ck_entries_confidence",
        ),
        CheckConstraint("priority >= 0 AND priority <= 100", name="ck_entries_priority"),
        CheckConstraint(
            "superseded_by_entry_id IS NULL OR superseded_by_entry_id <> id",
            name="ck_entries_not_self_superseded",
        ),
        Index("ix_entries_owner_scope", "user_id", "scope_kind", "scope_id"),
        Index("ix_entries_owner_status_type", "user_id", "status", "type"),
        Index("ix_entries_owner_subject", "user_id", "subject_type", "subject_id"),
        Index("ix_entries_owner_updated", "user_id", "updated_at"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    scope_kind: Mapped[str] = mapped_column(String(20))
    scope_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    subject_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    subject_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject_data: Mapped[dict] = mapped_column(JSONDict, default=dict)

    type: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16), default="captured")
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSONDict, default=dict)
    provenance: Mapped[dict] = mapped_column(JSONDict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=50)

    created_at_chapter_id: Mapped[str | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True, index=True
    )
    superseded_by_entry_id: Mapped[str | None] = mapped_column(
        ForeignKey("entries.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
