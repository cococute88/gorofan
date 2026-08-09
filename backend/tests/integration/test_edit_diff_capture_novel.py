"""Path B — Novel continuation capture (P1-7 design §6.3, §10.1, §17).

Drives the real SSE continuation endpoint with a recording provider, so every
assertion here is about what the production write path actually persisted.
"""
from __future__ import annotations

import hashlib
import logging
from collections.abc import AsyncIterator
from functools import partial
from itertools import count
from typing import Any, cast

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from starlette.testclient import TestClient

from app.adapters.base import AssembledPrompt, Completion, ModelCapability, ProviderRequest
from app.config import get_settings
from app.models.edit_diff import EditDiffCapture
from app.repositories.chapter_repository import ChapterRepository, chapter_for_update_stmt
from app.repositories.edit_diff_repository import EditDiffCaptureRepository
from app.services.edit_diff_capture import (
    SOURCE_KIND_CHAPTER_CONTINUATION,
    EditDiffCaptureService,
)
from app.services.novel_service import NovelService

SEGMENT = "이어쓰기완료"


class _RecordingAdapter:
    TOKENS = ["이어", "쓰기", "완료"]

    async def stream_chat(
        self, prompt: AssembledPrompt, req: ProviderRequest
    ) -> AsyncIterator[str]:
        for token in self.TOKENS:
            yield token

    async def chat(self, prompt: AssembledPrompt, req: ProviderRequest) -> Completion:
        return Completion(content=SEGMENT, token_count=3, finish_reason="stop")

    def capabilities(self, model: str) -> ModelCapability:
        return ModelCapability(context_window=8192, max_output_tokens=1024)


class _FailingAdapter(_RecordingAdapter):
    """Streams two tokens, then fails — the existing partial-append path."""

    async def stream_chat(
        self, prompt: AssembledPrompt, req: ProviderRequest
    ) -> AsyncIterator[str]:
        yield "이어"
        yield "쓰기"
        raise RuntimeError("provider exploded")


@pytest.fixture()
def novel_client():
    from app.main import create_app

    manager = TestClient(create_app())
    client = manager.__enter__()
    try:
        cast(Any, client.app).state.registry.register("fake", _RecordingAdapter)
        client.post(
            "/api/v1/model-configs",
            json={
                "provider": "fake",
                "model_name": "fake-1",
                "max_tokens": 256,
                "context_window": 8192,
                "is_default": True,
            },
        )
        yield client
    finally:
        manager.__exit__(None, None, None)


def _setup(client, *, title: str, content: str = "그는 문을 열었다.") -> tuple[str, str]:
    work = client.post("/api/v1/works", json={"title": title}).json()
    chapter = client.post(
        f"/api/v1/works/{work['id']}/chapters",
        json={"title": "1화", "content_text": content},
    ).json()
    return work["id"], chapter["id"]


def _continue(client, chapter_id: str):
    return client.post(
        f"/api/v1/works/chapters/{chapter_id}/continue",
        json={"instruction": "이어써라", "target_words": 50},
    )


def _run(client, function, *args, **kwargs):
    assert client.portal is not None
    return client.portal.call(
        partial(function, client.app.state.sessionmaker, *args, **kwargs)
    )


async def _captures_for(sessionmaker, chapter_id: str) -> list[EditDiffCapture]:
    async with sessionmaker() as session:
        stmt = (
            select(EditDiffCapture)
            .where(EditDiffCapture.chapter_id == chapter_id)
            .order_by(EditDiffCapture.sequence)
        )
        return list((await session.execute(stmt)).scalars().all())


def _chapter(client, work_id: str, chapter_id: str) -> dict:
    chapters = client.get(f"/api/v1/works/{work_id}/chapters").json()
    return next(c for c in chapters if c["id"] == chapter_id)


def test_a_continuation_writes_one_unsettled_capture(novel_client) -> None:
    work_id, chapter_id = _setup(novel_client, title="포착1")
    assert _continue(novel_client, chapter_id).status_code == 200

    rows = _run(novel_client, _captures_for, chapter_id)
    assert len(rows) == 1
    row = rows[0]
    assert row.source_kind == SOURCE_KIND_CHAPTER_CONTINUATION
    assert row.chapter_id == chapter_id
    assert row.entry_id is None
    assert row.user_id == get_settings().DEFAULT_USER_ID
    assert row.sequence == 0
    # Byte-exact streamed provider output.
    assert row.before_text == SEGMENT
    assert row.before_chars == len(SEGMENT)
    # Unsettled is the normal state for a fresh Path B row.
    assert row.settled_at is None
    assert row.after_state is None
    assert row.after_text is None
    assert row.after_sha256 is None
    assert row.after_chars is None
    assert row.producer == "novel.continue.v1"
    assert row.context["insert_offset"] == len("그는 문을 열었다.")
    assert row.context["chapter_version"] == _chapter(novel_client, work_id, chapter_id)["version"]
    assert row.context["partial_stream"] is False
    assert row.context["asset_id"] == "novel.continue"
    assert row.context["asset_version"] == "v1"
    assert row.context["provider"] == "fake"
    assert row.context["model"] == "fake-1"
    assert "settle_trigger" not in row.context


def test_successive_continuations_increment_the_sequence(novel_client) -> None:
    _work_id, chapter_id = _setup(novel_client, title="포착2")
    assert _continue(novel_client, chapter_id).status_code == 200
    assert _continue(novel_client, chapter_id).status_code == 200

    rows = _run(novel_client, _captures_for, chapter_id)
    assert [row.sequence for row in rows] == [0, 1]
    assert all(row.before_text == SEGMENT for row in rows)


def test_the_stream_error_path_marks_partial_and_keeps_the_provider_error(
    novel_client,
) -> None:
    cast(Any, novel_client.app).state.registry.register("fake", _FailingAdapter)
    try:
        _work_id, chapter_id = _setup(novel_client, title="부분실패")
        response = _continue(novel_client, chapter_id)
        assert "event: error" in response.text
    finally:
        cast(Any, novel_client.app).state.registry.register("fake", _RecordingAdapter)

    rows = _run(novel_client, _captures_for, chapter_id)
    assert len(rows) == 1
    assert rows[0].context["partial_stream"] is True
    assert rows[0].before_text == "이어쓰기"


def test_capture_failure_rolls_the_append_back(novel_client, monkeypatch) -> None:
    """Tier 2: no capture, no merged segment. The author's text is untouched."""
    work_id, chapter_id = _setup(novel_client, title="티어2")
    original = _chapter(novel_client, work_id, chapter_id)

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("induced capture failure")

    monkeypatch.setattr(
        EditDiffCaptureService, "capture_chapter_continuation", _boom
    )

    with pytest.raises(RuntimeError, match="induced capture failure"):
        _continue(novel_client, chapter_id)

    after = _chapter(novel_client, work_id, chapter_id)
    assert after["content_text"] == original["content_text"]
    assert after["version"] == original["version"]
    assert _run(novel_client, _captures_for, chapter_id) == []


def test_a_capture_failure_never_masks_the_provider_error(
    novel_client, monkeypatch, caplog
) -> None:
    cast(Any, novel_client.app).state.registry.register("fake", _FailingAdapter)

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("induced capture failure")

    monkeypatch.setattr(
        EditDiffCaptureService, "capture_chapter_continuation", _boom
    )
    try:
        _work_id, chapter_id = _setup(novel_client, title="에러우선")
        with caplog.at_level(logging.WARNING):
            response = _continue(novel_client, chapter_id)
        assert "event: error" in response.text
        assert "provider exploded" in response.text
        assert "induced capture failure" not in response.text
    finally:
        cast(Any, novel_client.app).state.registry.register("fake", _RecordingAdapter)

    warnings = [r for r in caplog.records if r.getMessage().startswith("edit_diff.")]
    assert warnings, "the capture failure must still be reported"
    _assert_no_prose(warnings)
    assert _run(novel_client, _captures_for, chapter_id) == []


def _assert_no_prose(records: list[logging.LogRecord]) -> None:
    """Captured author prose must never reach a log line (design §9.3)."""
    for record in records:
        rendered = record.getMessage() + repr(getattr(record, "meta", {}))
        for fragment in (SEGMENT, "이어", "그는 문을 열었다."):
            assert fragment not in rendered


def test_an_author_save_captures_nothing(novel_client) -> None:
    work_id, chapter_id = _setup(novel_client, title="자동저장")
    before = _chapter(novel_client, work_id, chapter_id)

    response = novel_client.patch(
        f"/api/v1/works/chapters/{chapter_id}",
        json={"content_text": "작가가 고쳐 쓴 문장.", "version": before["version"]},
    )
    assert response.status_code == 200
    # The 1.2s autosave is deliberately not a capture point and not a settle
    # trigger: it would record "the human changed nothing" (design §6.3.1).
    assert _run(novel_client, _captures_for, chapter_id) == []


def test_deleting_a_chapter_removes_its_captures(novel_client) -> None:
    _work_id, chapter_id = _setup(novel_client, title="삭제")
    assert _continue(novel_client, chapter_id).status_code == 200
    assert _run(novel_client, _captures_for, chapter_id)

    assert novel_client.delete(f"/api/v1/works/chapters/{chapter_id}").status_code in (
        200,
        204,
    )
    assert _run(novel_client, _captures_for, chapter_id) == []


def test_the_chapter_lock_is_a_real_row_lock() -> None:
    """SQLite ignores FOR UPDATE, so assert on the compiled PostgreSQL form."""
    compiled = str(
        chapter_for_update_stmt("chapter-1", user_id="user-1").compile(
            dialect=postgresql.dialect()
        )
    )
    assert "FOR UPDATE" in compiled
    assert "chapters" in compiled


def test_the_append_path_locks_before_deriving_the_sequence(
    novel_client, monkeypatch
) -> None:
    # Session identity matters: the settle pass also locks the chapter, so a
    # bare "a lock happened" assertion would still pass with the append's own
    # lock removed. The sequence must be derived in a session that holds it.
    order: list[tuple[str, int]] = []
    original_lock = ChapterRepository.get_for_update
    original_sequence = EditDiffCaptureRepository.next_sequence
    counter = count()

    def _key(session) -> int:  # noqa: ANN001
        # session.info is per-instance, so this survives address reuse between
        # a closed session and the next one.
        if "lock_spy" not in session.info:
            session.info["lock_spy"] = next(counter)
        return session.info["lock_spy"]

    async def _spy_lock(self, session, chapter_id, *, user_id):  # noqa: ANN001
        order.append(("lock", _key(session)))
        return await original_lock(self, session, chapter_id, user_id=user_id)

    async def _spy_sequence(self, session, **kwargs):  # noqa: ANN001
        order.append(("sequence", _key(session)))
        return await original_sequence(self, session, **kwargs)

    monkeypatch.setattr(ChapterRepository, "get_for_update", _spy_lock)
    monkeypatch.setattr(EditDiffCaptureRepository, "next_sequence", _spy_sequence)

    _work_id, chapter_id = _setup(novel_client, title="락순서")
    assert _continue(novel_client, chapter_id).status_code == 200

    sequence_events = [i for i, (kind, _) in enumerate(order) if kind == "sequence"]
    assert sequence_events, "the append path must derive a capture sequence"
    for index in sequence_events:
        _kind, session_id = order[index]
        held = [
            other
            for other, (kind, other_session) in enumerate(order[:index])
            if kind == "lock" and other_session == session_id
        ]
        assert held, "MAX(sequence)+1 was derived without holding the chapter lock"


def test_the_capture_calls_are_not_wrapped_in_bare_swallows() -> None:
    import inspect

    source = inspect.getsource(NovelService._append_chapter)
    assert "capture_chapter_continuation" in source
    assert "except Exception" not in source


# --- settle (design §6.3, Tier 3) -------------------------------------------


def test_the_next_continuation_settles_the_previous_capture(novel_client) -> None:
    work_id, chapter_id = _setup(novel_client, title="정착")
    assert _continue(novel_client, chapter_id).status_code == 200

    # The author revises before asking for more prose — this is the signal.
    current = _chapter(novel_client, work_id, chapter_id)
    revised = "그는 문을 부수듯 열었다.\n\n작가가 다듬은 문장."
    assert (
        novel_client.patch(
            f"/api/v1/works/chapters/{chapter_id}",
            json={"content_text": revised, "version": current["version"]},
        ).status_code
        == 200
    )

    assert _continue(novel_client, chapter_id).status_code == 200

    rows = _run(novel_client, _captures_for, chapter_id)
    assert len(rows) == 2
    first, second = rows

    assert first.settled_at is not None
    assert first.after_state == "stored"
    assert first.after_text == revised
    assert first.after_chars == len(revised)
    assert first.after_sha256 == hashlib.sha256(revised.encode("utf-8")).hexdigest()
    assert first.context["settle_trigger"] == "next-continuation"
    # The before-side is untouched by settling.
    assert first.before_text == SEGMENT

    # The new row is the one now pending.
    assert second.sequence == 1
    assert second.settled_at is None


def test_a_replayed_settle_changes_nothing(novel_client) -> None:
    """The `settled_at IS NULL` guard makes a second settle affect zero rows."""
    _work_id, chapter_id = _setup(novel_client, title="재정착")
    assert _continue(novel_client, chapter_id).status_code == 200

    service = cast(Any, novel_client.app).state.novel_service
    user_id = get_settings().DEFAULT_USER_ID
    assert novel_client.portal is not None
    settle = partial(service._settle_chapter_captures, user_id, chapter_id)

    novel_client.portal.call(settle)
    first = _run(novel_client, _captures_for, chapter_id)[0]
    assert first.settled_at is not None

    novel_client.portal.call(settle)
    second = _run(novel_client, _captures_for, chapter_id)[0]
    assert second.settled_at == first.settled_at
    assert second.after_sha256 == first.after_sha256


def test_the_trailing_capture_stays_pending(novel_client) -> None:
    """A chapter whose last continuation is never followed keeps one pending row.

    That is a normal terminal state, not a gap: the after-side lives in
    `chapters.content_text` and is resolved at read time (design §6.3.1).
    """
    work_id, chapter_id = _setup(novel_client, title="마지막")
    assert _continue(novel_client, chapter_id).status_code == 200

    rows = _run(novel_client, _captures_for, chapter_id)
    assert len(rows) == 1
    assert rows[0].settled_at is None
    # The after-side is obtainable for free, forever.
    assert _chapter(novel_client, work_id, chapter_id)["content_text"].endswith(SEGMENT)


def test_a_settle_failure_does_not_block_the_continuation(
    novel_client, monkeypatch, caplog
) -> None:
    """Tier 3 is best effort — but reported, and the row stays pending."""
    _work_id, chapter_id = _setup(novel_client, title="정착실패")
    assert _continue(novel_client, chapter_id).status_code == 200

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("induced settle failure")

    monkeypatch.setattr(EditDiffCaptureService, "settle_chapter_captures", _boom)

    with caplog.at_level(logging.WARNING):
        response = _continue(novel_client, chapter_id)
    assert response.status_code == 200
    assert "event: done" in response.text

    rows = _run(novel_client, _captures_for, chapter_id)
    assert len(rows) == 2
    assert rows[0].settled_at is None, "a failed settle must leave the row pending"

    warnings = [
        record
        for record in caplog.records
        if record.getMessage() == "edit_diff.settle_failed"
    ]
    assert len(warnings) == 1
    assert warnings[0].meta["chapter_id"] == chapter_id
    assert warnings[0].meta["failure_class"] == "RuntimeError"
    _assert_no_prose(warnings)


def test_a_later_continuation_can_still_settle_a_missed_row(
    novel_client, monkeypatch
) -> None:
    _work_id, chapter_id = _setup(novel_client, title="재시도")
    assert _continue(novel_client, chapter_id).status_code == 200

    async def _boom(*_args, **_kwargs):
        raise RuntimeError("induced settle failure")

    monkeypatch.setattr(EditDiffCaptureService, "settle_chapter_captures", _boom)
    assert _continue(novel_client, chapter_id).status_code == 200
    monkeypatch.undo()

    assert _continue(novel_client, chapter_id).status_code == 200

    rows = _run(novel_client, _captures_for, chapter_id)
    assert len(rows) == 3
    assert [row.settled_at is not None for row in rows] == [True, True, False]


def test_the_settle_path_takes_the_chapter_lock(novel_client, monkeypatch) -> None:
    order: list[str] = []
    original_lock = ChapterRepository.get_for_update
    original_settle = EditDiffCaptureService.settle_chapter_captures

    async def _spy_lock(self, session, chapter_id, *, user_id):  # noqa: ANN001
        order.append("lock")
        return await original_lock(self, session, chapter_id, user_id=user_id)

    async def _spy_settle(self, session, **kwargs):  # noqa: ANN001
        order.append("settle")
        return await original_settle(self, session, **kwargs)

    _work_id, chapter_id = _setup(novel_client, title="정착락")
    assert _continue(novel_client, chapter_id).status_code == 200

    monkeypatch.setattr(ChapterRepository, "get_for_update", _spy_lock)
    monkeypatch.setattr(EditDiffCaptureService, "settle_chapter_captures", _spy_settle)
    assert _continue(novel_client, chapter_id).status_code == 200

    assert order[0] == "lock"
    assert order[1] == "settle"


def test_the_settle_call_is_reported_not_swallowed() -> None:
    import inspect

    source = inspect.getsource(NovelService._settle_chapter_captures)
    assert "settle_chapter_captures" in source
    # Tier 3 may catch, but never silently.
    assert "pass" not in source.split("except Exception")[-1].split("\n")[1]
    assert "_logger.warning" in source
