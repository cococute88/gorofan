"""P1-6 end-to-end: Entry Store canon reaching real Chat/Novel generation.

Drives the actual SSE endpoints with a recording provider so the assembled
prompt can be inspected. Covers the flag OFF/ON contract, retrieval call counts,
owner/scope/status isolation, block separation, and the streaming/CAS behaviour
that must survive the new pre-stream retrieval step.
"""
from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.adapters.base import AssembledPrompt, Completion, ModelCapability, ProviderRequest
from app.config import FEATURE_ENTRY_STORE_CONTEXT, get_settings
from app.core.errors import Conflict
from app.models.entry import Entry
from app.models.novel import Chapter
from app.models.user import User
from app.schemas.entry import EntryScope, EntryStatus, EntryType
from app.services import entry_generation_context as entry_generation_context_module
from app.services import novel_service as novel_service_module
from app.services.entry_generation_context import ENTRY_CONTEXT_LIMIT
from app.services.entry_service import EntryService
from app.services.novel_service import NovelService

_CAPTURED: list[AssembledPrompt] = []


class _RecordingAdapter:
    """Deterministic provider that records every assembled prompt it receives."""

    TOKENS = ["이어", "쓰기", "완료"]

    async def stream_chat(
        self, prompt: AssembledPrompt, req: ProviderRequest
    ) -> AsyncIterator[str]:
        _CAPTURED.append(prompt)
        for token in self.TOKENS:
            yield token

    async def chat(self, prompt: AssembledPrompt, req: ProviderRequest) -> Completion:
        _CAPTURED.append(prompt)
        return Completion(content="".join(self.TOKENS), token_count=3, finish_reason="stop")

    def capabilities(self, model: str) -> ModelCapability:
        return ModelCapability(context_window=8192, max_output_tokens=1024)


@pytest.fixture(autouse=True)
def _clear_captured():
    _CAPTURED.clear()
    yield
    _CAPTURED.clear()


@pytest.fixture()
def make_client():
    """Build an app whose Settings carry an explicit P1-6 feature-flag value."""

    from starlette.testclient import TestClient

    from app.main import create_app

    opened = []

    def _make(*, entry_context: bool):
        settings = get_settings().model_copy(
            update={"FEATURES": {FEATURE_ENTRY_STORE_CONTEXT: entry_context}}
        )
        manager = TestClient(create_app(settings))
        client = manager.__enter__()
        opened.append(manager)
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
        return client

    yield _make
    for manager in reversed(opened):
        manager.__exit__(None, None, None)


@pytest.fixture()
def retrieve_calls(monkeypatch):
    """Count real ``EntryService.retrieve()`` invocations without stubbing it."""

    calls: list[object] = []
    original = EntryService.retrieve

    async def _counting(self, session, request):  # noqa: ANN001
        calls.append(request)
        return await original(self, session, request)

    monkeypatch.setattr(EntryService, "retrieve", _counting)
    return calls


# --- helpers ----------------------------------------------------------------


def _owner_id() -> str:
    return get_settings().DEFAULT_USER_ID


def _entry(
    *,
    content: str,
    scope_kind: EntryScope,
    scope_id: str | None = None,
    entry_type: EntryType = EntryType.STORY_FACT,
    status: EntryStatus = EntryStatus.CANON,
    user_id: str | None = None,
    priority: int = 100,
    subject_type: str | None = None,
    subject_id: str | None = None,
    data: dict[str, object] | None = None,
    created_at_chapter_id: str | None = None,
    provenance: dict[str, object] | None = None,
) -> Entry:
    return Entry(
        user_id=user_id or _owner_id(),
        scope_kind=scope_kind.value,
        scope_id=scope_id,
        subject_type=subject_type,
        subject_id=subject_id,
        subject_data={},
        type=entry_type.value,
        status=status.value,
        title=None,
        content=content,
        data=data or {},
        provenance=provenance
        or {
            "source_kind": "user",
            "capture_method": "human-authored",
            "producer": "p1-6-test",
        },
        priority=priority,
        created_at_chapter_id=created_at_chapter_id,
        accepted_at=datetime(2026, 1, 1, tzinfo=UTC) if status is EntryStatus.CANON else None,
    )


def _write(*rows) -> list[str]:
    """Persist fixture rows through an independent connection to the test DB.

    Returns the persisted ids. The suite shares one SQLite file across test
    modules, and this owner's ``user``-scoped canon is legitimately reachable
    from every request, so assertions here identify *these* rows rather than
    counting everything the Store happens to hold.
    """

    async def _run() -> list[str]:
        engine = create_async_engine(os.environ["DATABASE_URL"])
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with sessionmaker() as session:
            session.add_all(list(rows))
            await session.commit()
            ids = [row.id for row in rows]
        await engine.dispose()
        return ids

    return asyncio.run(_run())


def _set_chapter_summary(chapter_id: str, summary: str) -> None:
    async def _run() -> None:
        engine = create_async_engine(os.environ["DATABASE_URL"])
        sessionmaker = async_sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession
        )
        async with sessionmaker() as session:
            chapter = await session.get(Chapter, chapter_id)
            assert chapter is not None
            chapter.summary = summary
            await session.commit()
        await engine.dispose()

    asyncio.run(_run())


def _hard_delete_chapter(chapter_id: str) -> None:
    async def _run() -> None:
        engine = create_async_engine(os.environ["DATABASE_URL"])
        sessionmaker = async_sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession
        )
        async with sessionmaker() as session:
            chapter = await session.get(Chapter, chapter_id)
            assert chapter is not None
            await session.delete(chapter)
            await session.commit()
        await engine.dispose()

    asyncio.run(_run())


def _foreign_owner() -> str:
    user = User(email=f"foreign-{datetime.now(UTC).timestamp()}@example.com", display_name="foreign")

    async def _run() -> str:
        engine = create_async_engine(os.environ["DATABASE_URL"])
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with sessionmaker() as session:
            session.add(user)
            await session.commit()
            await session.refresh(user)
        await engine.dispose()
        return user.id

    return asyncio.run(_run())


def _chat_setup(client, *, character_name: str, world_name: str) -> tuple[str, str, str]:
    world = client.post(
        "/api/v1/worlds", json={"name": world_name, "description": "설명"}
    ).json()
    character = client.post(
        "/api/v1/characters", json={"name": character_name, "world_id": world["id"]}
    ).json()
    chat = client.post("/api/v1/chats", json={"character_id": character["id"]}).json()
    return world["id"], character["id"], chat["id"]


def _novel_setup(client, *, title: str, world_name: str) -> tuple[str, str, str]:
    world = client.post(
        "/api/v1/worlds", json={"name": world_name, "description": "설명"}
    ).json()
    work = client.post(
        "/api/v1/works", json={"title": title, "world_id": world["id"]}
    ).json()
    chapter = client.post(
        f"/api/v1/works/{work['id']}/chapters",
        json={"title": "1화", "content_text": "그는 문을 열었다."},
    ).json()
    return world["id"], work["id"], chapter["id"]


def _prompt_text(prompt: AssembledPrompt) -> str:
    return "\n".join(message.content for message in prompt.messages)


def _entry_kinds(prompt: AssembledPrompt) -> list[str]:
    return [e["kind"] for e in prompt.trace["entries"] if e["kind"] == "entry"]


def _entry_block_ids(prompt: AssembledPrompt) -> list[str]:
    return [e["block_id"] for e in prompt.trace["entries"] if e["kind"] == "entry"]


def _identity(prompt: AssembledPrompt) -> tuple:
    """The provider-visible payload — what "byte-identical" has to mean."""

    return (
        tuple((m.role, m.content) for m in prompt.messages),
        prompt.system,
        prompt.token_count,
    )


# --- Chat: flag OFF ---------------------------------------------------------


def test_flag_off_makes_entry_data_irrelevant_to_the_chat_prompt(
    make_client, retrieve_calls
) -> None:
    client = make_client(entry_context=False)

    # Two identically-configured characters; only the second one has canon.
    _, _, bare_chat = _chat_setup(client, character_name="루나", world_name="아르카디아")
    _, seeded_character, seeded_chat = _chat_setup(
        client, character_name="루나", world_name="아르카디아"
    )
    _write(
        _entry(
            content="루나는 왼손잡이 검사다.",
            scope_kind=EntryScope.CHARACTER,
            scope_id=seeded_character,
            entry_type=EntryType.CHARACTER_IDENTITY,
        )
    )

    client.post(f"/api/v1/chats/{bare_chat}/messages", json={"content": "안녕?"})
    client.post(f"/api/v1/chats/{seeded_chat}/messages", json={"content": "안녕?"})

    assert len(_CAPTURED) == 2
    without_canon, with_canon = _CAPTURED
    # Flag OFF: the presence of canon changes nothing that reaches the provider.
    assert _identity(without_canon) == _identity(with_canon)
    assert "루나는 왼손잡이 검사다." not in _prompt_text(with_canon)
    assert _entry_kinds(with_canon) == []
    assert with_canon.trace["entry_context"] == {
        "feature_enabled": False,
        "retrieval_invoked": False,
    }
    # And no Entry retrieval was performed at all.
    assert retrieve_calls == []


# --- Chat: flag ON ----------------------------------------------------------


def test_flag_on_injects_canon_into_the_chat_prompt_exactly_once(
    make_client, retrieve_calls
) -> None:
    client = make_client(entry_context=True)
    world_id, character_id, chat_id = _chat_setup(
        client, character_name="세라", world_name="에테르니아"
    )
    voice_id, world_fact_id = _write(
        _entry(
            content="세라는 낮은 목소리로 천천히 말한다.",
            scope_kind=EntryScope.CHARACTER,
            scope_id=character_id,
            entry_type=EntryType.CHARACTER_VOICE,
        ),
        _entry(
            content="에테르니아의 마력은 달빛에서 나온다.",
            scope_kind=EntryScope.WORLD,
            scope_id=world_id,
            entry_type=EntryType.WORLD_FACT,
        ),
    )

    client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": "세라, 마력이 뭐야?"})

    assert len(retrieve_calls) == 1, "retrieval must run exactly once per turn"
    prompt = _CAPTURED[0]
    text = _prompt_text(prompt)
    assert "세라는 낮은 목소리로 천천히 말한다." in text
    assert "에테르니아의 마력은 달빛에서 나온다." in text
    assert {f"entry:{voice_id}", f"entry:{world_fact_id}"} <= set(_entry_block_ids(prompt))

    trace = prompt.trace["entry_context"]
    assert trace["feature_enabled"] is True
    assert trace["retrieval_invoked"] is True
    assert trace["task_kind"] == "chat"
    assert {voice_id, world_fact_id} <= set(trace["selected_entry_ids"])
    assert trace["blocks_created"] is True
    assert trace["no_eligible_entries"] is False


def test_chat_declares_no_work_scope_and_excludes_work_canon(
    make_client, retrieve_calls
) -> None:
    client = make_client(entry_context=True)
    world_id, character_id, chat_id = _chat_setup(
        client, character_name="카이", world_name="노바"
    )
    work_id = client.post(
        "/api/v1/works", json={"title": "다른 작품", "world_id": world_id}
    ).json()["id"]
    _write(
        _entry(
            content="카이는 은퇴한 기사다.",
            scope_kind=EntryScope.CHARACTER,
            scope_id=character_id,
            entry_type=EntryType.CHARACTER_IDENTITY,
        ),
        _entry(
            content="이 작품에서 황제는 3화에 죽는다.",
            scope_kind=EntryScope.WORK,
            scope_id=work_id,
        ),
    )

    client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": "카이 누구야?"})

    request = retrieve_calls[0]
    assert EntryScope.WORK not in {selector.scope_kind for selector in request.scopes}

    text = _prompt_text(_CAPTURED[0])
    assert "카이는 은퇴한 기사다." in text
    # Chat must not guess which work the conversation belongs to (RFC-003 §13.3).
    assert "이 작품에서 황제는 3화에 죽는다." not in text


def test_chat_excludes_non_canon_and_foreign_owner_entries(
    make_client, retrieve_calls
) -> None:
    client = make_client(entry_context=True)
    world_id, character_id, chat_id = _chat_setup(
        client, character_name="리안", world_name="테라"
    )
    foreign_id = _foreign_owner()
    _write(
        _entry(
            content="리안은 canon 사실이다.",
            scope_kind=EntryScope.CHARACTER,
            scope_id=character_id,
            entry_type=EntryType.CHARACTER_IDENTITY,
        ),
        _entry(
            content="리안은 proposed 제안이다.",
            scope_kind=EntryScope.CHARACTER,
            scope_id=character_id,
            status=EntryStatus.PROPOSED,
        ),
        _entry(
            content="리안은 rejected 제안이다.",
            scope_kind=EntryScope.CHARACTER,
            scope_id=character_id,
            status=EntryStatus.REJECTED,
        ),
        _entry(
            content="리안은 superseded 옛 사실이다.",
            scope_kind=EntryScope.CHARACTER,
            scope_id=character_id,
            status=EntryStatus.SUPERSEDED,
        ),
        _entry(
            content="리안은 captured 초안이다.",
            scope_kind=EntryScope.CHARACTER,
            scope_id=character_id,
            status=EntryStatus.CAPTURED,
        ),
        _entry(
            content="다른 사용자의 canon 이다.",
            scope_kind=EntryScope.WORLD,
            scope_id=world_id,
            user_id=foreign_id,
        ),
    )

    client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": "리안?"})

    text = _prompt_text(_CAPTURED[0])
    assert "리안은 canon 사실이다." in text
    for excluded in (
        "리안은 proposed 제안이다.",
        "리안은 rejected 제안이다.",
        "리안은 superseded 옛 사실이다.",
        "리안은 captured 초안이다.",
        "다른 사용자의 canon 이다.",
    ):
        assert excluded not in text
    assert retrieve_calls[0].status_filters is None


def test_chat_excludes_entries_whose_scope_anchor_is_soft_deleted(
    make_client, retrieve_calls
) -> None:
    """The orphaned anchor is a *declared, reachable* scope — only the filter drops it."""

    client = make_client(entry_context=True)
    world_id, character_id, chat_id = _chat_setup(
        client, character_name="오르카", world_name="사라질세계"
    )
    live_id, orphaned_id = _write(
        _entry(
            content="오르카는 살아있는 앵커의 사실이다.",
            scope_kind=EntryScope.CHARACTER,
            scope_id=character_id,
            entry_type=EntryType.CHARACTER_IDENTITY,
        ),
        _entry(
            content="고아가 된 세계의 사실이다.",
            scope_kind=EntryScope.WORLD,
            scope_id=world_id,
            entry_type=EntryType.WORLD_FACT,
        ),
    )
    assert client.delete(f"/api/v1/worlds/{world_id}").status_code == 204

    client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": "오르카?"})

    # The chat still declares the world scope; the Entry is dropped because its
    # anchor is soft-deleted, not because the scope was unreachable.
    assert world_id in {selector.scope_id for selector in retrieve_calls[0].scopes}
    trace = _CAPTURED[0].trace["entry_context"]
    assert orphaned_id in trace["retrieval_exclusions"]["orphaned_entry_ids"]
    assert orphaned_id not in trace["selected_entry_ids"]
    assert live_id in trace["selected_entry_ids"]

    text = _prompt_text(_CAPTURED[0])
    assert "오르카는 살아있는 앵커의 사실이다." in text
    assert "고아가 된 세계의 사실이다." not in text


def test_chat_keeps_lore_memory_and_entry_as_separate_blocks(make_client) -> None:
    client = make_client(entry_context=True)
    world_id, character_id, chat_id = _chat_setup(
        client, character_name="미르", world_name="글라시아"
    )
    lorebook = client.post(
        f"/api/v1/worlds/{world_id}/lorebooks", json={"name": "기본"}
    ).json()
    client.post(
        f"/api/v1/worlds/lorebooks/{lorebook['id']}/entries",
        json={"keywords": ["빙하"], "content": "레거시 로어: 빙하는 신성하다.", "enabled": True},
    )
    _write(
        _entry(
            content="미르는 빙하 위에서 태어났다.",
            scope_kind=EntryScope.CHARACTER,
            scope_id=character_id,
            entry_type=EntryType.CHARACTER_IDENTITY,
        )
    )

    client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": "빙하 이야기 해줘"})

    prompt = _CAPTURED[0]
    kinds = [e["kind"] for e in prompt.trace["entries"]]
    text = _prompt_text(prompt)

    assert "lore" in kinds and "entry" in kinds
    assert "레거시 로어: 빙하는 신성하다." in text  # legacy scanner preserved
    assert "미르는 빙하 위에서 태어났다." in text
    # The Entry block is its own kind, never relabelled as chat-private memory.
    entry_ids = [e["block_id"] for e in prompt.trace["entries"] if e["kind"] == "entry"]
    memory_ids = [e["block_id"] for e in prompt.trace["entries"] if e["kind"] == "memory"]
    assert entry_ids and all(bid.startswith("entry:") for bid in entry_ids)
    assert not set(entry_ids) & set(memory_ids)


def test_regenerate_also_retrieves_exactly_once(make_client, retrieve_calls) -> None:
    """Regenerate shares the T1 path, so it must not double- or skip-retrieve."""

    client = make_client(entry_context=True)
    _, character_id, chat_id = _chat_setup(client, character_name="아린", world_name="설원")
    entry_id = _write(
        _entry(
            content="아린은 눈보라 속에서 자랐다.",
            scope_kind=EntryScope.CHARACTER,
            scope_id=character_id,
            entry_type=EntryType.CHARACTER_IDENTITY,
        )
    )[0]

    client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": "아린 얘기 해줘"})
    assert len(retrieve_calls) == 1

    regen = client.post(f"/api/v1/chats/{chat_id}/regenerate")
    assert regen.status_code == 200, regen.text

    assert len(retrieve_calls) == 2, "one retrieval for the turn, one for the regenerate"
    assert entry_id in _CAPTURED[1].trace["entry_context"]["selected_entry_ids"]


def test_considered_candidate_count_matches_what_the_real_ranker_scored(
    make_client, retrieve_calls
) -> None:
    """Seed past the retrieval limit so production really rejects ranked candidates.

    Drives the actual endpoint, so the count is checked against the trace that
    `EntryService.retrieve()` itself produced rather than a re-derived formula.
    """

    client = make_client(entry_context=True)
    _, character_id, chat_id = _chat_setup(client, character_name="하람", world_name="다우림")
    _write(
        *[
            _entry(
                content=f"하람에 대한 사실 {index}.",
                scope_kind=EntryScope.CHARACTER,
                scope_id=character_id,
                entry_type=EntryType.CHARACTER_IDENTITY,
            )
            for index in range(ENTRY_CONTEXT_LIMIT + 5)
        ]
    )

    client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": "하람 얘기 해줘"})

    assert len(retrieve_calls) == 1
    trace = _CAPTURED[0].trace["entry_context"]
    exclusions = trace["retrieval_exclusions"]

    # The limit is a real, exercised path here, not a hypothetical.
    assert trace["selected_count"] == ENTRY_CONTEXT_LIMIT
    assert exclusions["limit_rejected_entry_ids"]

    assert trace["considered_candidate_count"] == (
        trace["selected_count"]
        + len(exclusions["retrieval_budget_rejected_entry_ids"])
        + len(exclusions["limit_rejected_entry_ids"])
    )
    # Orphan filtering runs before ranking, so it never inflates the count.
    for orphan_id in exclusions["orphaned_entry_ids"]:
        assert orphan_id not in trace["selected_entry_ids"]
    assert trace["considered_candidate_count"] >= trace["selected_count"]


def test_chat_sse_contract_and_single_persist_survive_entry_injection(
    make_client,
) -> None:
    client = make_client(entry_context=True)
    _, character_id, chat_id = _chat_setup(client, character_name="유나", world_name="바다")
    _write(
        _entry(
            content="유나는 바다를 무서워한다.",
            scope_kind=EntryScope.CHARACTER,
            scope_id=character_id,
            entry_type=EntryType.CHARACTER_IDENTITY,
        )
    )

    response = client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": "안녕?"})

    assert response.status_code == 200, response.text
    body = response.text
    assert body.index("event: token") < body.index("event: done")

    messages = client.get(f"/api/v1/chats/{chat_id}/messages").json()["items"]
    assert [m["content"] for m in messages if m["role"] == "user"] == ["안녕?"]
    replies = [m for m in messages if m["role"] == "assistant" and m["content"] == "이어쓰기완료"]
    assert len(replies) == 1


# --- Novel ------------------------------------------------------------------


def test_flag_off_makes_entry_data_irrelevant_to_the_novel_prompt(
    make_client, retrieve_calls
) -> None:
    client = make_client(entry_context=False)
    _, _, bare_chapter = _novel_setup(client, title="연대기", world_name="북방")
    _, seeded_work, seeded_chapter = _novel_setup(client, title="연대기", world_name="북방")
    _write(
        _entry(
            content="황제는 이미 죽었다.",
            scope_kind=EntryScope.WORK,
            scope_id=seeded_work,
        )
    )

    payload = {"instruction": "이어써라", "target_words": 100}
    client.post(f"/api/v1/works/chapters/{bare_chapter}/continue", json=payload)
    client.post(f"/api/v1/works/chapters/{seeded_chapter}/continue", json=payload)

    assert len(_CAPTURED) == 2
    without_canon, with_canon = _CAPTURED
    assert _identity(without_canon) == _identity(with_canon)
    assert "황제는 이미 죽었다." not in _prompt_text(with_canon)
    assert _entry_kinds(with_canon) == []
    assert with_canon.trace["entry_context"] == {
        "feature_enabled": False,
        "retrieval_invoked": False,
    }
    assert retrieve_calls == []


def test_flag_on_injects_work_canon_into_the_novel_prompt_exactly_once(
    make_client, retrieve_calls
) -> None:
    client = make_client(entry_context=True)
    world_id, work_id, chapter_id = _novel_setup(client, title="검의 노래", world_name="아스칼")
    other_work = client.post("/api/v1/works", json={"title": "무관한 작품"}).json()["id"]
    sword_id, world_fact_id, foreign_work_id = _write(
        _entry(content="주인공의 검은 부러졌다.", scope_kind=EntryScope.WORK, scope_id=work_id),
        _entry(
            content="아스칼에는 겨울이 없다.",
            scope_kind=EntryScope.WORLD,
            scope_id=world_id,
            entry_type=EntryType.WORLD_FACT,
        ),
        _entry(
            content="다른 작품의 비밀이다.",
            scope_kind=EntryScope.WORK,
            scope_id=other_work,
        ),
    )

    response = client.post(
        f"/api/v1/works/chapters/{chapter_id}/continue",
        json={"instruction": "검에 대해 이어써라", "target_words": 100},
    )
    assert response.status_code == 200, response.text

    assert len(retrieve_calls) == 1
    request = retrieve_calls[0]
    assert request.task_kind.value == "scene"
    assert (EntryScope.WORK, work_id) in {(s.scope_kind, s.scope_id) for s in request.scopes}

    text = _prompt_text(_CAPTURED[0])
    assert "주인공의 검은 부러졌다." in text
    assert "아스칼에는 겨울이 없다." in text
    # Work canon never bleeds across works (RFC-003 §7.2).
    assert "다른 작품의 비밀이다." not in text

    trace = _CAPTURED[0].trace["entry_context"]
    assert {sword_id, world_fact_id} <= set(trace["selected_entry_ids"])
    assert foreign_work_id not in trace["selected_entry_ids"]
    assert trace["entry_block_tokens"] > 0


def test_novel_append_and_version_cas_survive_entry_injection(make_client) -> None:
    client = make_client(entry_context=True)
    _, work_id, chapter_id = _novel_setup(client, title="회귀록", world_name="제국")
    _write(
        _entry(content="주인공은 회귀자다.", scope_kind=EntryScope.WORK, scope_id=work_id)
    )
    before = client.get(f"/api/v1/works/{work_id}/chapters").json()[0]

    response = client.post(
        f"/api/v1/works/chapters/{chapter_id}/continue",
        json={"instruction": "이어써라", "target_words": 100},
    )
    assert response.status_code == 200, response.text
    assert "event: done" in response.text

    after = client.get(f"/api/v1/works/{work_id}/chapters").json()[0]
    assert after["version"] == before["version"] + 1
    assert after["content_text"].endswith("이어쓰기완료")
    assert after["content_text"].startswith("그는 문을 열었다.")


def test_novel_retrieval_failure_is_not_swallowed(make_client, monkeypatch) -> None:
    """Pre-stream context failures abort the turn, as they already do for memory/lore."""

    client = make_client(entry_context=True)
    _, work_id, chapter_id = _novel_setup(client, title="실패작", world_name="공허")

    async def _boom(self, session, request):  # noqa: ANN001
        raise RuntimeError("entry store unavailable")

    monkeypatch.setattr(EntryService, "retrieve", _boom)

    with pytest.raises(RuntimeError, match="entry store unavailable"):
        client.post(
            f"/api/v1/works/chapters/{chapter_id}/continue",
            json={"instruction": "이어써라", "target_words": 100},
        )

    # Nothing was streamed or appended on the failure path.
    assert _CAPTURED == []
    chapter = client.get(f"/api/v1/works/{work_id}/chapters").json()[0]
    assert chapter["content_text"] == "그는 문을 열었다."


def test_novel_provider_receives_only_prior_summaries_in_story_order(
    make_client, retrieve_calls
) -> None:
    client = make_client(entry_context=True)
    work = client.post("/api/v1/works", json={"title": "Chronology"}).json()
    chapters = [
        client.post(
            f"/api/v1/works/{work['id']}/chapters",
            json={"title": f"{index}", "content_text": f"chapter {index}"},
        ).json()
        for index in range(1, 8)
    ]
    chapter_1, chapter_2, target, *_middle, chapter_7 = chapters
    summary_1, summary_2, current, future, unknown = _write(
        _entry(
            content="SUMMARY ONE",
            scope_kind=EntryScope.WORK,
            scope_id=work["id"],
            entry_type=EntryType.STORY_SUMMARY,
            subject_type="chapter",
            subject_id=chapter_1["id"],
            priority=1,
            created_at_chapter_id=chapter_2["id"],
        ),
        _entry(
            content="SUMMARY TWO",
            scope_kind=EntryScope.WORK,
            scope_id=work["id"],
            entry_type=EntryType.STORY_SUMMARY,
            subject_type="chapter",
            subject_id=chapter_2["id"],
            priority=100,
        ),
        _entry(
            content="CURRENT LEAK",
            scope_kind=EntryScope.WORK,
            scope_id=work["id"],
            entry_type=EntryType.STORY_SUMMARY,
            subject_type="chapter",
            subject_id=target["id"],
            priority=100,
        ),
        _entry(
            content="FUTURE LEAK " * 100,
            scope_kind=EntryScope.WORK,
            scope_id=work["id"],
            entry_type=EntryType.STORY_SUMMARY,
            subject_type="chapter",
            subject_id=chapter_7["id"],
            priority=100,
        ),
        _entry(
            content="UNKNOWN LEAK",
            scope_kind=EntryScope.WORK,
            scope_id=work["id"],
            entry_type=EntryType.STORY_SUMMARY,
            subject_type="work",
            subject_id=work["id"],
            priority=100,
        ),
    )

    response = client.post(
        f"/api/v1/works/chapters/{target['id']}/continue",
        json={"instruction": "continue", "target_words": 100},
    )

    assert response.status_code == 200, response.text
    assert len(_CAPTURED) == 1
    text = _prompt_text(_CAPTURED[0])
    assert text.index("SUMMARY ONE") < text.index("SUMMARY TWO")
    assert "CURRENT LEAK" not in text
    assert "FUTURE LEAK" not in text
    assert "UNKNOWN LEAK" not in text
    trace = _CAPTURED[0].trace["entry_context"]
    assert [
        entry_id
        for entry_id in trace["selected_entry_ids"]
        if entry_id in {summary_1, summary_2}
    ] == [summary_1, summary_2]
    chronology_exclusions = {
        item["entry_id"]: item["reason"]
        for item in trace["retrieval_exclusions"]["story_summary_chronology"]
    }
    assert {
        entry_id: chronology_exclusions[entry_id]
        for entry_id in (current, future, unknown)
    } == {
        current: "current_chapter_summary",
        future: "future_chapter_summary",
        unknown: "missing_chapter_subject",
    }
    assert future not in trace["retrieval_exclusions"][
        "retrieval_budget_rejected_entry_ids"
    ]
    assert future not in trace["retrieval_exclusions"]["limit_rejected_entry_ids"]
    assert len(retrieve_calls) == 1


def test_novel_excludes_deleted_required_provenance_before_assembly_and_prompt(
    make_client,
) -> None:
    client = make_client(entry_context=True)
    work = client.post("/api/v1/works", json={"title": "Provenance"}).json()
    subject, provenance_source, normal_subject, target = [
        client.post(
            f"/api/v1/works/{work['id']}/chapters",
            json={"title": str(index), "content_text": f"chapter {index}"},
        ).json()
        for index in range(1, 5)
    ]
    broken_id, normal_id = _write(
        _entry(
            content="BROKEN PROVENANCE MUST NOT REACH PROVIDER " * 100,
            scope_kind=EntryScope.WORK,
            scope_id=work["id"],
            entry_type=EntryType.STORY_SUMMARY,
            subject_type="chapter",
            subject_id=subject["id"],
            priority=100,
            provenance={
                "source_kind": "chapter",
                "source_id": provenance_source["id"],
                "capture_method": "ai-extracted",
                "producer": "deleted-provenance-test",
            },
        ),
        _entry(
            content="NORMAL PRIOR SURVIVES",
            scope_kind=EntryScope.WORK,
            scope_id=work["id"],
            entry_type=EntryType.STORY_SUMMARY,
            subject_type="chapter",
            subject_id=normal_subject["id"],
            priority=1,
        ),
    )
    _hard_delete_chapter(provenance_source["id"])

    response = client.post(
        f"/api/v1/works/chapters/{target['id']}/continue",
        json={"instruction": "continue", "target_words": 100},
    )

    assert response.status_code == 200, response.text
    assert len(_CAPTURED) == 1
    prompt = _CAPTURED[0]
    assert "BROKEN PROVENANCE MUST NOT REACH PROVIDER" not in _prompt_text(prompt)
    assert "NORMAL PRIOR SURVIVES" in _prompt_text(prompt)
    assert f"entry:{broken_id}" not in _entry_block_ids(prompt)
    assert f"entry:{normal_id}" in _entry_block_ids(prompt)
    trace = prompt.trace["entry_context"]
    assert normal_id in trace["selected_entry_ids"]
    assert broken_id not in trace["selected_entry_ids"]
    assert {
        item["entry_id"]: item["reason"]
        for item in trace["retrieval_exclusions"]["story_summary_chronology"]
    }[broken_id] == "invalid_required_provenance_anchor"
    assert broken_id not in trace["retrieval_exclusions"][
        "retrieval_budget_rejected_entry_ids"
    ]
    assert broken_id not in trace["retrieval_exclusions"]["limit_rejected_entry_ids"]


def test_novel_interleaves_legacy_and_entry_summaries_by_story_order(make_client) -> None:
    client = make_client(entry_context=True)
    work = client.post("/api/v1/works", json={"title": "Mixed chronology"}).json()
    chapter_1, chapter_2, target = [
        client.post(
            f"/api/v1/works/{work['id']}/chapters",
            json={"title": str(index), "content_text": f"chapter {index}"},
        ).json()
        for index in range(1, 4)
    ]
    _set_chapter_summary(chapter_1["id"], "LEGACY CHAPTER ONE")
    _write(
        _entry(
            content="ENTRY CHAPTER TWO",
            scope_kind=EntryScope.WORK,
            scope_id=work["id"],
            entry_type=EntryType.STORY_SUMMARY,
            subject_type="chapter",
            subject_id=chapter_2["id"],
        )
    )

    response = client.post(
        f"/api/v1/works/chapters/{target['id']}/continue",
        json={"instruction": "continue", "target_words": 100},
    )

    assert response.status_code == 200, response.text
    text = _prompt_text(_CAPTURED[0])
    assert text.index("LEGACY CHAPTER ONE") < text.index("ENTRY CHAPTER TWO")


@pytest.mark.parametrize("legacy_summary", ["", "   ", "\n\n", "legacy prose"])
def test_novel_legacy_substantive_predicate_applies_with_flag_off(
    make_client, legacy_summary: str
) -> None:
    client = make_client(entry_context=False)
    _, work_id, target_id = _novel_setup(
        client, title=f"legacy-{repr(legacy_summary)}", world_name="Legacy World"
    )
    _set_chapter_summary(target_id, legacy_summary)
    next_chapter = client.post(
        f"/api/v1/works/{work_id}/chapters",
        json={"title": "2", "content_text": "next"},
    ).json()

    response = client.post(
        f"/api/v1/works/chapters/{next_chapter['id']}/continue",
        json={"instruction": "continue", "target_words": 100},
    )

    assert response.status_code == 200, response.text
    text = _prompt_text(_CAPTURED[0])
    if legacy_summary.strip():
        assert "legacy prose" in text
    else:
        assert not any(
            item["kind"] == "chapter" for item in _CAPTURED[0].trace["entries"]
        )


def test_novel_reorder_during_preparation_uses_one_pre_reorder_view(
    make_client, monkeypatch
) -> None:
    client = make_client(entry_context=True)
    work = client.post("/api/v1/works", json={"title": "Concurrent"}).json()
    source = client.post(
        f"/api/v1/works/{work['id']}/chapters",
        json={"title": "S", "content_text": "source"},
    ).json()
    target = client.post(
        f"/api/v1/works/{work['id']}/chapters",
        json={"title": "T", "content_text": "target"},
    ).json()

    async def _set_initial() -> None:
        sessionmaker = cast(Any, client.app).state.sessionmaker
        async with sessionmaker() as session:
            rows = list(
                (
                    await session.execute(
                        select(Chapter).where(Chapter.work_id == work["id"])
                    )
                ).scalars().all()
            )
            for chapter in rows:
                chapter.index += 100000
            await session.flush()
            by_id = {chapter.id: chapter for chapter in rows}
            by_id[source["id"]].index = 2
            by_id[source["id"]].summary = "CONSISTENT LEGACY SOURCE"
            by_id[target["id"]].index = 10
            await session.commit()

    asyncio.run(_set_initial())
    entry_id = _write(
        _entry(
            content="CONSISTENT ENTRY SOURCE",
            scope_kind=EntryScope.WORK,
            scope_id=work["id"],
            entry_type=EntryType.STORY_SUMMARY,
            subject_type="chapter",
            subject_id=source["id"],
        )
    )[0]
    original = NovelService._build_story_context
    reordered = False

    async def _reorder_between_target_and_evidence(self, session, loaded_work, chapter):  # noqa: ANN001
        nonlocal reordered
        if not reordered:
            reordered = True
            async with self.sm() as writer:
                rows = list(
                    (
                        await writer.execute(
                            select(Chapter).where(Chapter.work_id == work["id"])
                        )
                    ).scalars().all()
                )
                for row in rows:
                    row.index += 100000
                await writer.flush()
                by_id = {row.id: row for row in rows}
                by_id[target["id"]].index = 3
                by_id[source["id"]].index = 4
                await writer.commit()
        return await original(self, session, loaded_work, chapter)

    monkeypatch.setattr(
        NovelService, "_build_story_context", _reorder_between_target_and_evidence
    )

    response = client.post(
        f"/api/v1/works/chapters/{target['id']}/continue",
        json={"instruction": "continue", "target_words": 100},
    )

    assert response.status_code == 200, response.text
    assert reordered is True
    assert len(_CAPTURED) == 1
    text = _prompt_text(_CAPTURED[0])
    assert text.count("CONSISTENT LEGACY SOURCE") == 1
    assert "CONSISTENT ENTRY SOURCE" not in text
    exclusions = _CAPTURED[0].trace["entry_context"]["retrieval_exclusions"][
        "story_summary_chronology"
    ]
    assert exclusions == [
        {
            "entry_id": entry_id,
            "disposition": "prior",
            "reason": "legacy_summary_authority_overlap",
            "source_chapter_id": source["id"],
            "source_chapter_index": 2,
        }
    ]
    after = client.get(f"/api/v1/works/{work['id']}/chapters").json()
    assert [(chapter["id"], chapter["index"]) for chapter in after] == [
        (target["id"], 3),
        (source["id"], 4),
    ]


def test_stale_anchor_fails_before_assembly_prompt_and_provider(
    make_client, monkeypatch
) -> None:
    client = make_client(entry_context=True)
    _, _work_id, target_id = _novel_setup(
        client, title="Stale", world_name="Stale World"
    )
    calls = {"retrieval": 0, "assembly": 0, "prompt": 0}
    original_factory = novel_service_module.build_novel_retrieve_request
    original_retrieve = EntryService.retrieve
    original_assembly = entry_generation_context_module.assemble_entry_context
    novel_engine = cast(Any, client.app).state.novel_service.engine
    original_prompt = novel_engine.assemble_continue

    def _stale_factory(**kwargs):  # noqa: ANN003, ANN202
        request = original_factory(**kwargs)
        policy = request.story_summary_chronology
        assert policy is not None
        stale_anchor = policy.anchor.model_copy(
            update={"chapter_index": policy.anchor.chapter_index + 1}
        )
        return request.model_copy(
            update={
                "story_summary_chronology": policy.model_copy(
                    update={"anchor": stale_anchor}
                )
            }
        )

    async def _count_retrieval(self, session, request):  # noqa: ANN001
        calls["retrieval"] += 1
        return await original_retrieve(self, session, request)

    def _count_assembly(request):  # noqa: ANN001, ANN202
        calls["assembly"] += 1
        return original_assembly(request)

    def _count_prompt(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        calls["prompt"] += 1
        return original_prompt(*args, **kwargs)

    monkeypatch.setattr(
        novel_service_module, "build_novel_retrieve_request", _stale_factory
    )
    monkeypatch.setattr(EntryService, "retrieve", _count_retrieval)
    monkeypatch.setattr(
        entry_generation_context_module, "assemble_entry_context", _count_assembly
    )
    monkeypatch.setattr(
        novel_engine,
        "assemble_continue",
        _count_prompt,
    )

    with pytest.raises(RuntimeError, match="response already started") as error:
        client.post(
            f"/api/v1/works/chapters/{target_id}/continue",
            json={"instruction": "continue", "target_words": 100},
        )

    assert isinstance(error.value.__cause__, Conflict)
    assert "anchor drifted" in str(error.value.__cause__)
    assert calls == {"retrieval": 1, "assembly": 0, "prompt": 0}
    assert _CAPTURED == []


def test_reorder_after_preparation_keeps_immutable_context_without_provider_lock(
    make_client, monkeypatch
) -> None:
    client = make_client(entry_context=True)
    work = client.post("/api/v1/works", json={"title": "After preparation"}).json()
    source = client.post(
        f"/api/v1/works/{work['id']}/chapters",
        json={"title": "S", "content_text": "source"},
    ).json()
    target = client.post(
        f"/api/v1/works/{work['id']}/chapters",
        json={"title": "T", "content_text": "target"},
    ).json()
    _set_chapter_summary(source["id"], "PREPARED LEGACY CONTEXT")
    reorder_committed_before_provider = False

    async def _reorder_after_preparation(self, user_id, chapter_id):  # noqa: ANN001
        nonlocal reorder_committed_before_provider
        async with self.sm() as writer:
            rows = list(
                (
                    await writer.execute(
                        select(Chapter).where(Chapter.work_id == work["id"])
                    )
                ).scalars().all()
            )
            for row in rows:
                row.index += 100000
            await writer.flush()
            by_id = {row.id: row for row in rows}
            by_id[target["id"]].index = 1
            by_id[source["id"]].index = 2
            await writer.commit()
        reorder_committed_before_provider = True

    monkeypatch.setattr(
        NovelService, "_settle_chapter_captures", _reorder_after_preparation
    )

    response = client.post(
        f"/api/v1/works/chapters/{target['id']}/continue",
        json={"instruction": "continue", "target_words": 100},
    )

    assert response.status_code == 200, response.text
    assert reorder_committed_before_provider is True
    assert len(_CAPTURED) == 1
    assert "PREPARED LEGACY CONTEXT" in _prompt_text(_CAPTURED[0])
    after = client.get(f"/api/v1/works/{work['id']}/chapters").json()
    assert [(chapter["id"], chapter["index"]) for chapter in after] == [
        (target["id"], 1),
        (source["id"], 2),
    ]
