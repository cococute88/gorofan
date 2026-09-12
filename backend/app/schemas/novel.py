"""Novel DTOs (design 6)."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.scene_generation import (
    SCENE_GOAL_MAX_LENGTH,
    SCENE_ITEM_MAX_LENGTH,
    SCENE_ITEMS_MAX_COUNT,
    SceneGenerationInput,
    normalize_scene_generation_input,
)
from app.core.scene_generation import (
    SCENE_TOTAL_MAX_LENGTH as SCENE_TOTAL_MAX_LENGTH,
)
from app.schemas.common import TimestampedOut


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


SceneItem = Annotated[str, Field(max_length=SCENE_ITEM_MAX_LENGTH)]


class SceneGenerationRequest(BaseModel):
    """Ephemeral structured intent for one Chapter generation request."""

    model_config = ConfigDict(extra="forbid")

    goal: str | None = Field(default=None, max_length=SCENE_GOAL_MAX_LENGTH)
    beats: list[SceneItem] = Field(
        default_factory=list, max_length=SCENE_ITEMS_MAX_COUNT
    )
    must_include: list[SceneItem] = Field(
        default_factory=list, max_length=SCENE_ITEMS_MAX_COUNT
    )
    must_avoid: list[SceneItem] = Field(
        default_factory=list, max_length=SCENE_ITEMS_MAX_COUNT
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_scene(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        raw = dict(value)
        normalized = normalize_scene_generation_input(
            goal=raw.get("goal"),
            beats=raw.get("beats", ()),
            must_include=raw.get("must_include", ()),
            must_avoid=raw.get("must_avoid", ()),
        )
        scene = normalized or SceneGenerationInput()
        raw.update(
            goal=scene.goal,
            beats=list(scene.beats),
            must_include=list(scene.must_include),
            must_avoid=list(scene.must_avoid),
        )
        return raw


class ContinueRequest(BaseModel):
    instruction: str = ""
    target_words: int = Field(default=800, ge=50, le=5000)
    client_request_id: str | None = None
    scene: SceneGenerationRequest | None = None


class WorkCharacterLink(BaseModel):
    character_id: str
    role_in_work: str = "조연"


class WorkCharacterOut(TimestampedOut):
    work_id: str
    character_id: str
    role_in_work: str
