"""Character / Persona DTOs (design 6)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import TimestampedOut


class CharacterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    world_id: str | None = None
    avatar_url: str | None = None
    greeting: str = ""
    speech_style: str = ""
    personality: str = ""
    tags: list[str] = Field(default_factory=list)


class CharacterUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    world_id: str | None = None
    avatar_url: str | None = None
    greeting: str | None = None
    speech_style: str | None = None
    personality: str | None = None
    tags: list[str] | None = None


class CharacterOut(TimestampedOut):
    user_id: str
    world_id: str | None
    name: str
    avatar_url: str | None
    greeting: str
    speech_style: str
    personality: str
    tags: list[str]


class PersonaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""


class PersonaUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    description: str | None = None


class PersonaOut(TimestampedOut):
    user_id: str
    name: str
    description: str
