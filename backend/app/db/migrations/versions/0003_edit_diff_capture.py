"""Add the P1-7 edit-diff capture table.

Additive and forward-only: one new non-Entry operational table, no ALTER on any
existing table, and no backfill (none is possible — every past edit already
destroyed its pre-image). See docs/architecture/edit-diff-capture-design.md §14.

Revision ID: 0003_edit_diff_capture
Revises: 0002_entry_store
Create Date: 2026-08-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_edit_diff_capture"
down_revision = "0002_entry_store"
branch_labels = None
depends_on = None

EDIT_DIFF_SOURCE_KIND_VALUES = ("entry-review-edit", "chapter-continuation")
EDIT_DIFF_PAYLOAD_STATE_VALUES = ("stored", "oversize")


def _json_type() -> sa.JSON:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.create_table(
        "edit_diff_captures",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("entry_id", sa.String(length=36), nullable=True),
        sa.Column("chapter_id", sa.String(length=36), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("before_state", sa.String(length=16), nullable=False),
        sa.Column("after_state", sa.String(length=16), nullable=True),
        sa.Column("before_text", sa.Text(), nullable=True),
        sa.Column("after_text", sa.Text(), nullable=True),
        sa.Column("before_sha256", sa.String(length=64), nullable=False),
        sa.Column("after_sha256", sa.String(length=64), nullable=True),
        sa.Column("before_chars", sa.Integer(), nullable=False),
        sa.Column("after_chars", sa.Integer(), nullable=True),
        sa.Column("producer", sa.String(length=120), nullable=True),
        sa.Column("context", _json_type(), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
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
            f"source_kind IN ({_quoted(EDIT_DIFF_SOURCE_KIND_VALUES)})",
            name="ck_edit_diff_captures_source_kind",
        ),
        sa.CheckConstraint(
            f"before_state IN ({_quoted(EDIT_DIFF_PAYLOAD_STATE_VALUES)})",
            name="ck_edit_diff_captures_before_state",
        ),
        sa.CheckConstraint(
            f"after_state IS NULL OR after_state IN ({_quoted(EDIT_DIFF_PAYLOAD_STATE_VALUES)})",
            name="ck_edit_diff_captures_after_state",
        ),
        sa.CheckConstraint(
            "(entry_id IS NOT NULL AND chapter_id IS NULL)"
            " OR (entry_id IS NULL AND chapter_id IS NOT NULL)",
            name="ck_edit_diff_captures_one_source",
        ),
        sa.CheckConstraint("sequence >= 0", name="ck_edit_diff_captures_sequence"),
        sa.CheckConstraint(
            "before_chars >= 0", name="ck_edit_diff_captures_before_chars"
        ),
        sa.CheckConstraint(
            "after_chars IS NULL OR after_chars >= 0",
            name="ck_edit_diff_captures_after_chars",
        ),
        sa.CheckConstraint(
            "(before_state = 'stored' AND before_text IS NOT NULL)"
            " OR (before_state = 'oversize' AND before_text IS NULL)",
            name="ck_edit_diff_captures_before_payload",
        ),
        sa.CheckConstraint(
            "after_state IS NULL"
            " OR (after_state = 'stored' AND after_text IS NOT NULL)"
            " OR (after_state = 'oversize' AND after_text IS NULL)",
            name="ck_edit_diff_captures_after_payload",
        ),
        sa.CheckConstraint(
            "(settled_at IS NULL"
            " AND after_state IS NULL AND after_sha256 IS NULL AND after_chars IS NULL)"
            " OR (settled_at IS NOT NULL"
            " AND after_state IS NOT NULL AND after_sha256 IS NOT NULL"
            " AND after_chars IS NOT NULL)",
            name="ck_edit_diff_captures_settled",
        ),
        sa.CheckConstraint(
            "source_kind <> 'entry-review-edit' OR settled_at IS NOT NULL",
            name="ck_edit_diff_captures_entry_settled",
        ),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entry_id"], ["entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entry_id", "sequence", name="uq_edit_diff_captures_entry_sequence"
        ),
        sa.UniqueConstraint(
            "chapter_id", "sequence", name="uq_edit_diff_captures_chapter_sequence"
        ),
    )
    op.create_index(
        "ix_edit_diff_captures_user_id",
        "edit_diff_captures",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_edit_diff_captures_owner_created",
        "edit_diff_captures",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_edit_diff_captures_owner_kind_settled",
        "edit_diff_captures",
        ["user_id", "source_kind", "settled_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("edit_diff_captures")
