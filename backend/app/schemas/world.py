"""World / Lore / Glossary DTOs (design 6)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, TimestampedOut


class WorldCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    era: str = ""
    races: list[str] = Field(default_factory=list)
    nations: list[str] = Field(default_factory=list)
    taboos: list[str] = Field(default_factory=list)


class WorldUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    era: str | None = None
    races: list[str] | None = None
    nations: list[str] | None = None
    taboos: list[str] | None = None


class WorldOut(TimestampedOut):
    user_id: str
    name: str
    description: str
    era: str
    races: list[str]
    nations: list[str]
    taboos: list[str]


class LorebookCreate(BaseModel):
    name: str = "기본 로어북"
    enabled: bool = True


class LorebookOut(TimestampedOut):
    world_id: str
    name: str
    enabled: bool


class LoreEntryCreate(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    content: str = ""
    priority: int = 50
    enabled: bool = True
    scan_depth: int = Field(default=4, ge=1, le=50)


class LoreEntryOut(TimestampedOut):
    lorebook_id: str
    keywords: list[str]
    content: str
    priority: int
    enabled: bool
    scan_depth: int


class GlossaryCreate(BaseModel):
    term: str = Field(min_length=1, max_length=200)
    definition: str = ""


class GlossaryOut(TimestampedOut):
    world_id: str
    term: str
    definition: str
