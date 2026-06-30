"""Novel DTOs (design 6)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, TimestampedOut


class WorkCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    synopsis: str = ""
    genre: str = ""
    world_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class WorkUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    synopsis: str | None = None
    genre: str | None = None
    world_id: str | None = None
    tags: list[str] | None = None


class WorkOut(TimestampedOut):
    user_id: str
    world_id: str | None
    title: str
    synopsis: str
    genre: str
    tags: list[str]


class ChapterCreate(BaseModel):
    title: str = ""
    content_text: str = ""


class ChapterUpdate(BaseModel):
    title: str | None = None
    content_doc: dict | None = None
    content_text: str | None = None
    version: int  # required for optimistic concurrency (design 6.5)


class ChapterOut(TimestampedOut):
    work_id: str
    index: int
    title: str
    content_doc: dict
    content_text: str
    summary: str
    word_count: int
    version: int


class ReorderRequest(BaseModel):
    ordered_chapter_ids: list[str]


class ContinueRequest(BaseModel):
    instruction: str = ""
    target_words: int = Field(default=800, ge=50, le=5000)
    client_request_id: str | None = None


class WorkCharacterLink(BaseModel):
    character_id: str
    role_in_work: str = "조연"


class WorkCharacterOut(TimestampedOut):
    work_id: str
    character_id: str
    role_in_work: str
