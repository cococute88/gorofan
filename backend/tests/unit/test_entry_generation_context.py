"""P1-6 feature-flag boundary and the Chat/Novel retrieval-situation builders."""
from __future__ import annotations

from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import FEATURE_ENTRY_STORE_CONTEXT, Settings
from app.schemas.entry import (
    EntryRetrievalResult,
    EntryRetrievalTaskKind,
    EntryRetrievalTrace,
    EntryScope,
)
from app.services.entry_generation_context import (
    ENTRY_CONTEXT_BUDGET_RATIO,
    ENTRY_CONTEXT_LIMIT,
    ENTRY_CONTEXT_MIN_BUDGET,
    build_chat_retrieve_request,
    build_novel_retrieve_request,
    entry_context_budget,
    load_entry_context,
)


class _Row:
    def __init__(self, row_id: str, **extra: object) -> None:
        self.id = row_id
        for key, value in extra.items():
            setattr(self, key, value)


class _ExplodingSession:
    """Any attribute touch means an Entry query was attempted."""

    def __getattr__(self, name: str) -> object:  # pragma: no cover - guard
        raise AssertionError(f"session was used while the feature flag was OFF: {name}")


class _RecordingEntryService:
    def __init__(self) -> None:
        self.calls: list[object] = []

    async def retrieve(self, session, request):  # noqa: ANN001
        self.calls.append(request)
        return EntryRetrievalResult(
            items=[],
            total_estimated_tokens=0,
            requested_budget=request.budget,
            policy_version="entry-keyword-v1",
            trace=EntryRetrievalTrace(),
        )


def _settings(**features: bool) -> Settings:
    return Settings(FEATURES=dict(features))


# --- flag boundary ----------------------------------------------------------


def test_entry_store_context_flag_defaults_to_off() -> None:
    assert _settings().entry_store_context_enabled is False
    assert _settings().feature_enabled(FEATURE_ENTRY_STORE_CONTEXT) is False


def test_entry_store_context_flag_reads_the_features_map() -> None:
    enabled = _settings(**{FEATURE_ENTRY_STORE_CONTEXT: True})
    assert enabled.entry_store_context_enabled is True

    explicitly_off = _settings(**{FEATURE_ENTRY_STORE_CONTEXT: False})
    assert explicitly_off.entry_store_context_enabled is False

    unrelated = _settings(some_other_flag=True)
    assert unrelated.entry_store_context_enabled is False


@pytest.mark.asyncio
async def test_flag_off_touches_neither_session_nor_request_builder() -> None:
    def _explode():  # pragma: no cover - guard
        raise AssertionError("a retrieval request was built while the flag was OFF")

    service = _RecordingEntryService()
    context = await load_entry_context(
        cast(AsyncSession, _ExplodingSession()),
        settings=_settings(),
        request_factory=_explode,
        entry_service=cast(Any, service),
    )

    assert context.blocks == []
    assert context.trace == {"feature_enabled": False, "retrieval_invoked": False}
    assert service.calls == []


@pytest.mark.asyncio
async def test_flag_on_retrieves_exactly_once() -> None:
    service = _RecordingEntryService()
    request = build_chat_retrieve_request(
        user_id="owner",
        character=_Row("char-1"),
        world=_Row("world-1"),
        user_message="안녕",
        context_window=8192,
    )

    context = await load_entry_context(
        cast(AsyncSession, object()),
        settings=_settings(**{FEATURE_ENTRY_STORE_CONTEXT: True}),
        request_factory=lambda: request,
        entry_service=cast(Any, service),
    )

    assert len(service.calls) == 1
    assert service.calls[0] is request
    assert context.trace["feature_enabled"] is True
    assert context.trace["retrieval_invoked"] is True
    assert context.trace["no_eligible_entries"] is True
    assert context.blocks == []


# --- budget -----------------------------------------------------------------


def test_entry_budget_is_a_bounded_share_of_the_context_window() -> None:
    assert entry_context_budget(8192) == int(8192 * ENTRY_CONTEXT_BUDGET_RATIO)
    # Never larger than the window, and never below a usable floor.
    assert entry_context_budget(8192) < 8192
    assert entry_context_budget(64) == ENTRY_CONTEXT_MIN_BUDGET


# --- chat situation ---------------------------------------------------------


def test_chat_request_never_declares_a_work_scope() -> None:
    request = build_chat_retrieve_request(
        user_id="owner",
        character=_Row("char-1"),
        world=_Row("world-1"),
        user_message="루나에 대해 알려줘",
        context_window=8192,
    )

    scope_kinds = {selector.scope_kind for selector in request.scopes}
    assert EntryScope.WORK not in scope_kinds
    assert scope_kinds == {EntryScope.USER, EntryScope.WORLD, EntryScope.CHARACTER}
    assert request.task_kind is EntryRetrievalTaskKind.CHAT
    assert request.cast == ["char-1"]
    assert request.beat == "루나에 대해 알려줘"
    # Canon-only defaults are inherited, never widened here.
    assert request.status_filters is None
    assert request.include_rejected is False
    assert request.include_superseded is False
    assert request.limit == ENTRY_CONTEXT_LIMIT


def test_chat_request_omits_a_world_scope_when_the_character_has_no_world() -> None:
    request = build_chat_retrieve_request(
        user_id="owner",
        character=_Row("char-1"),
        world=None,
        user_message=None,
        context_window=8192,
    )

    assert [s.scope_kind for s in request.scopes] == [
        EntryScope.USER,
        EntryScope.CHARACTER,
    ]
    assert request.beat is None


def test_chat_request_is_deterministic() -> None:
    def _build():
        return build_chat_retrieve_request(
            user_id="owner",
            character=_Row("char-1"),
            world=_Row("world-1"),
            user_message="같은 질문",
            context_window=8192,
        )

    assert _build().model_dump() == _build().model_dump()


# --- novel situation --------------------------------------------------------


def test_novel_request_declares_work_world_and_cast() -> None:
    request = build_novel_retrieve_request(
        user_id="owner",
        work=_Row("work-1"),
        world=_Row("world-1"),
        characters=[_Row("char-b"), _Row("char-a")],
        chapter=_Row("chapter-1", content_text="마지막 문단입니다."),
        instruction="다음 장면을 이어써라",
        context_window=8192,
    )

    assert [(s.scope_kind, s.scope_id) for s in request.scopes] == [
        (EntryScope.USER, None),
        (EntryScope.WORK, "work-1"),
        (EntryScope.WORLD, "world-1"),
        (EntryScope.CHARACTER, "char-a"),
        (EntryScope.CHARACTER, "char-b"),
    ]
    assert request.cast == ["char-a", "char-b"]
    assert request.task_kind is EntryRetrievalTaskKind.SCENE
    assert request.beat == "다음 장면을 이어써라 마지막 문단입니다."
    assert request.status_filters is None


def test_novel_request_is_deterministic_regardless_of_cast_ordering() -> None:
    def _build(characters):
        return build_novel_retrieve_request(
            user_id="owner",
            work=_Row("work-1"),
            world=None,
            characters=characters,
            chapter=_Row("chapter-1", content_text="본문"),
            instruction=None,
            context_window=8192,
        )

    forward = _build([_Row("char-a"), _Row("char-b")])
    reverse = _build([_Row("char-b"), _Row("char-a")])

    assert forward.model_dump() == reverse.model_dump()
    assert forward.beat == "본문"
