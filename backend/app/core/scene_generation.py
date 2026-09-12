"""Shared domain contract for ephemeral Scene generation input."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

SCENE_GOAL_MAX_LENGTH = 1000
SCENE_ITEM_MAX_LENGTH = 500
SCENE_ITEMS_MAX_COUNT = 16
SCENE_TOTAL_MAX_LENGTH = 12000


class SceneGenerationValidationError(ValueError):
    """A Scene generation input violates the canonical domain contract."""


@dataclass(frozen=True)
class SceneGenerationInput:
    """Immutable provider-neutral scene intent for one generation only."""

    goal: str | None = None
    beats: tuple[str, ...] = ()
    must_include: tuple[str, ...] = ()
    must_avoid: tuple[str, ...] = ()


def normalize_scene_generation_input(
    *,
    goal: object = None,
    beats: object = (),
    must_include: object = (),
    must_avoid: object = (),
) -> SceneGenerationInput | None:
    """Validate and snapshot one Scene input without transport/runtime dependencies."""

    normalized_goal = _normalize_goal(goal)
    normalized_beats = _normalize_items(beats, "beats")
    normalized_must_include = _normalize_items(must_include, "must_include")
    normalized_must_avoid = _normalize_items(must_avoid, "must_avoid")
    total = len(normalized_goal or "") + sum(
        len(item)
        for values in (
            normalized_beats,
            normalized_must_include,
            normalized_must_avoid,
        )
        for item in values
    )
    if total > SCENE_TOTAL_MAX_LENGTH:
        raise SceneGenerationValidationError(
            f"scene text must not exceed {SCENE_TOTAL_MAX_LENGTH} characters"
        )

    scene = SceneGenerationInput(
        goal=normalized_goal,
        beats=normalized_beats,
        must_include=normalized_must_include,
        must_avoid=normalized_must_avoid,
    )
    if not (scene.goal or scene.beats or scene.must_include or scene.must_avoid):
        return None
    return scene


def _normalize_goal(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SceneGenerationValidationError("scene goal must be a string or null")
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > SCENE_GOAL_MAX_LENGTH:
        raise SceneGenerationValidationError(
            f"scene goal must not exceed {SCENE_GOAL_MAX_LENGTH} characters"
        )
    return normalized


def _normalize_items(value: object, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise SceneGenerationValidationError(f"scene {field_name} must be a non-string sequence")
    if len(value) > SCENE_ITEMS_MAX_COUNT:
        raise SceneGenerationValidationError(
            f"scene {field_name} must not contain more than {SCENE_ITEMS_MAX_COUNT} items"
        )

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise SceneGenerationValidationError(f"scene {field_name} items must be strings")
        text = item.strip()
        if not text:
            raise SceneGenerationValidationError("scene items must not be blank")
        if len(text) > SCENE_ITEM_MAX_LENGTH:
            raise SceneGenerationValidationError(
                f"scene items must not exceed {SCENE_ITEM_MAX_LENGTH} characters"
            )
        normalized.append(text)
    return tuple(normalized)
