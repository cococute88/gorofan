"""Add the RFC-002 Entry Store persistence foundation.

Revision ID: 0002_entry_store
Revises: 0001_initial
Create Date: 2026-07-12
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_entry_store"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

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


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.create_table(
        "entries",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("scope_kind", sa.String(length=20), nullable=False),
        sa.Column("scope_id", sa.String(length=36), nullable=True),
        sa.Column("subject_type", sa.String(length=32), nullable=True),
        sa.Column("subject_id", sa.String(length=255), nullable=True),
        sa.Column("subject_data", _json_type(), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("data", _json_type(), nullable=False),
        sa.Column("provenance", _json_type(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("created_at_chapter_id", sa.String(length=36), nullable=True),
        sa.Column("superseded_by_entry_id", sa.String(length=36), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"scope_kind IN ({_quoted(ENTRY_SCOPE_VALUES)})",
            name="ck_entries_scope_kind",
        ),
        sa.CheckConstraint(
            f"type IN ({_quoted(ENTRY_TYPE_VALUES)})",
            name="ck_entries_type",
        ),
        sa.CheckConstraint(
            f"status IN ({_quoted(ENTRY_STATUS_VALUES)})",
            name="ck_entries_status",
        ),
        sa.CheckConstraint(
            "length(trim(content)) > 0",
            name="ck_entries_content_nonempty",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="ck_entries_confidence",
        ),
        sa.CheckConstraint(
            "priority >= 0 AND priority <= 100",
            name="ck_entries_priority",
        ),
        sa.CheckConstraint(
            "superseded_by_entry_id IS NULL OR superseded_by_entry_id <> id",
            name="ck_entries_not_self_superseded",
        ),
        sa.ForeignKeyConstraint(
            ["created_at_chapter_id"], ["chapters.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by_entry_id"], ["entries.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_entries_created_at_chapter_id",
        "entries",
        ["created_at_chapter_id"],
        unique=False,
    )
    op.create_index(
        "ix_entries_owner_scope",
        "entries",
        ["user_id", "scope_kind", "scope_id"],
        unique=False,
    )
    op.create_index(
        "ix_entries_owner_status_type",
        "entries",
        ["user_id", "status", "type"],
        unique=False,
    )
    op.create_index(
        "ix_entries_owner_subject",
        "entries",
        ["user_id", "subject_type", "subject_id"],
        unique=False,
    )
    op.create_index(
        "ix_entries_owner_updated",
        "entries",
        ["user_id", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_entries_superseded_by_entry_id",
        "entries",
        ["superseded_by_entry_id"],
        unique=False,
    )
    op.create_index("ix_entries_user_id", "entries", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_table("entries")
