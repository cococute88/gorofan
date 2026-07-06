"""Declarative base + common mixins (design 4.1, 4.3).

All tables use UUID (string) PKs and created/updated timestamps. SQLite stores
UUID as TEXT and JSON as JSON; PostgreSQL maps to native UUID/JSONB via the
SQLAlchemy 2.0 type system — no raw SQL (design 4.4 / CON-2).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Shared declarative base."""


class UUIDMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )


class BaseModel(Base, UUIDMixin, TimestampMixin):
    """Base for entities with id + timestamps."""

    __abstract__ = True
