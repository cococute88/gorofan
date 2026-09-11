"""Novel DTOs (design 6)."""
from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


SCENE_GOAL_MAX_LENGTH = 1000
SCENE_ITEM_MAX_LENGTH = 500
SCENE_ITEMS_MAX_COUNT = 16
SCENE_TOTAL_MAX_LENGTH = 12000

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

    @field_validator("goal", mode="before")
    @classmethod
    def _normalize_goal(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("beats", "must_include", "must_avoid", mode="before")
    @classmethod
    def _normalize_items(cls, value: object) -> object:
        if value is None:
            return []
        if not isinstance(value, (list, tuple)):
            return value
        normalized: list[object] = []
        for item in value:
            if isinstance(item, str):
                item = item.strip()
                if not item:
                    raise ValueError("scene items must not be blank")
            normalized.append(item)
        return normalized

    @model_validator(mode="after")
    def _bound_total_text(self) -> SceneGenerationRequest:
        total = len(self.goal or "") + sum(
            len(item)
            for values in (self.beats, self.must_include, self.must_avoid)
            for item in values
        )
        if total > SCENE_TOTAL_MAX_LENGTH:
            raise ValueError(
                f"scene text must not exceed {SCENE_TOTAL_MAX_LENGTH} characters"
            )
        return self


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
