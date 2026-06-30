"""initial baseline schema

Creates all tables from the ORM metadata (design Phase 4). Keeping the baseline in
lockstep with models avoids drift for the MVP; subsequent changes use autogenerate.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-30
"""
from __future__ import annotations

from alembic import op

from app.db.base import Base
from app.models import *  # noqa: F401,F403

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
