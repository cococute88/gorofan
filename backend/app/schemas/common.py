"""Shared schema primitives (design 6.1)."""
from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TimestampedOut(ORMModel):
    id: str
    created_at: datetime
    updated_at: datetime


class PageOut(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None
