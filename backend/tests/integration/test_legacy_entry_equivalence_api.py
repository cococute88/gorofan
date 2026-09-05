"""P1-8 owner-safe, provider-free, non-mutating diagnostic API tests."""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from sqlalchemy import event, func, select

import app.engines.memory.engine as memory_engine_module
from app.config import get_settings
from app.engines.memory.engine import MemoryEngine, rank_memories
from app.models.character import Character
from app.models.chat import ChatSession, Memory, Message
from app.models.edit_diff import EditDiffCapture
from app.models.entry import Entry
from app.models.novel import Chapter, Work
from app.models.user import User
from app.models.world import Lorebook, LoreEntry, World
from app.services.entry_service import EntryService

_OVERRIDE = {
    "context_window": 4096,
    "max_tokens": 512,
    "safety_ratio": 0.08,
}


def _owner_id() -> str:
    return get_settings().DEFAULT_USER_ID


def _run(coro):  # noqa: ANN001, ANN202
    return asyncio.run(coro)


def _chat_fixture(client, suffix: str) -> dict[str, str]:  # noqa: ANN001
    world = client.post(
        "/api/v1/worlds",
        json={
            "name": f"진단세계-{suffix}",
            "description": "달빛이 마력의 근원이다.",
            "era": "왕국력 3세기",
            "races": ["인간", "엘프"],
            "nations": ["북부 왕국"],
            "taboos": ["검은 달을 부르지 않는다."],
        },
    ).json()
    character = client.post(
        "/api/v1/characters",
        json={
            "name": f"세라-{suffix}",
            "world_id": world["id"],
            "personality": "위기에도 침착하다.",
            "speech_style": "짧은 존댓말을 쓴다.",
            "greeting": "진단 투영 대상이 아니다.",
        },
    ).json()
    glossary = client.post(
        f"/api/v1/worlds/{world['id']}/glossary",
        json={"term": "월광", "definition": "달에서 흐르는 마력"},
    ).json()
    lorebook = client.post(
        f"/api/v1/worlds/{world['id']}/lorebooks",
        json={"name": "꺼진 책", "enabled": False},
    ).json()
    lore = client.post(
        f"/api/v1/worlds/lorebooks/{lorebook['id']}/entries",
        json={
            "keywords": ["달빛"],
            "content": "달빛 아래에서는 거짓말을 할 수 없다.",
            "priority": 50,
            "enabled": True,
            "scan_depth": 7,
        },
    ).json()
    chat = client.post(
        "/api/v1/chats", json={"character_id": character["id"]}
    ).json()
    return {
        "world": world["id"],
        "character": character["id"],
        "glossary": glossary["id"],
        "lore": lore["id"],
        "chat": chat["id"],
    }


def _canon(
    client,  # noqa: ANN001
    *,
    scope_kind: str,
    scope_id: str,
    subject_type: str,
    subject_id: str,
    entry_type: str,
    content: str,
    title: str | None = None,
    data: dict[str, object] | None = None,
    created_at_chapter_id: str | None = None,
    priority: int = 80,
) -> str:
    payload: dict[str, object] = {
        "scope_kind": scope_kind,
        "scope_id": scope_id,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "type": entry_type,
        "content": content,
        "data": data or {},
        "priority": priority,
    }
    if title is not None:
        payload["title"] = title
    if created_at_chapter_id is not None:
        payload["created_at_chapter_id"] = created_at_chapter_id
    response = client.post("/api/v1/entries", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _compare_chat(client, chat_id: str, *, mode: str, message: str | None = None):  # noqa: ANN001, ANN202
    chat: dict[str, object] = {"chat_id": chat_id, "mode": mode}
    if message is not None:
        chat["user_message"] = message
    return client.post(
        "/api/v1/entries/equivalence:compare",
        json={"chat": chat, "budget_override": _OVERRIDE},
    )


async def _chat_state(client, chat_id: str) -> tuple:  # noqa: ANN001
    sm = cast(Any, client.app).state.sessionmaker
    async with sm() as session:
        messages = list(
            (
                await session.execute(
                    select(Message)
                    .where(Message.chat_session_id == chat_id)
                    .order_by(Message.id)
                )
            ).scalars().all()
        )
        memories = list(
            (
                await session.execute(
                    select(Memory)
                    .where(Memory.chat_session_id == chat_id)
                    .order_by(Memory.id)
                )
            ).scalars().all()
        )
        captures = int(
            (
                await session.execute(select(func.count(EditDiffCapture.id)))
            ).scalar_one()
        )
        return (
            [(m.id, m.role, m.content, m.is_active, m.status) for m in messages],
            [(m.id, m.content, m.version) for m in memories],
            captures,
        )


async def _table_counts(client) -> tuple[int, ...]:  # noqa: ANN001
    sm = cast(Any, client.app).state.sessionmaker
    models = (
        Entry,
        Character,
        World,
        Lorebook,
        LoreEntry,
        ChatSession,
        Message,
        Memory,
        Chapter,
        EditDiffCapture,
    )
    async with sm() as session:
        counts: list[int] = []
        for model in models:
            count = (await session.execute(select(func.count(model.id)))).scalar_one()
            counts.append(int(count))
        return tuple(counts)


@pytest.fixture()
def retrieve_calls(monkeypatch):  # noqa: ANN201
    calls: list[object] = []
    original = EntryService.retrieve

    async def counting(self, session, request):  # noqa: ANN001, ANN202
        calls.append(request)
        return await original(self, session, request)

    monkeypatch.setattr(EntryService, "retrieve", counting)
    return calls


def test_chat_diagnostic_is_typed_deterministic_and_read_only(
    client, retrieve_calls, monkeypatch
) -> None:  # noqa: ANN001
    ids = _chat_fixture(client, "new")
    personality_id = _canon(
        client,
        scope_kind="character",
        scope_id=ids["character"],
        subject_type="character",
        subject_id=ids["character"],
        entry_type="character.identity",
        content="위기에도 침착하다.",
    )
    _canon(
        client,
        scope_kind="character",
        scope_id=ids["character"],
        subject_type="character",
        subject_id=ids["character"],
        entry_type="character.voice",
        content="짧은 존댓말을 쓴다.",
    )
    _canon(
        client,
        scope_kind="world",
        scope_id=ids["world"],
        subject_type="world",
        subject_id=ids["world"],
        entry_type="world.fact",
        content="달빛이 마력의 근원이다.",
    )
    _canon(
        client,
        scope_kind="world",
        scope_id=ids["world"],
        subject_type="world",
        subject_id=ids["world"],
        entry_type="world.term",
        title="월광",
        content="달에서 흐르는 마력",
    )
    _canon(
        client,
        scope_kind="world",
        scope_id=ids["world"],
        subject_type="world",
        subject_id=ids["world"],
        entry_type="world.fact",
        content="달빛 아래에서는 거짓말을 할 수 없다.",
    )

    async def provider_forbidden(*_args, **_kwargs):  # noqa: ANN001, ANN202
        raise AssertionError("diagnostic must not call a provider")
        yield  # pragma: no cover

    monkeypatch.setattr(
        cast(Any, client.app).state.registry,
        "stream_with_resilience",
        provider_forbidden,
    )
    writes: list[str] = []

    def capture_statement(_conn, _cursor, statement, *_args):  # noqa: ANN001, ANN202
        verb = statement.lstrip().split(None, 1)[0].upper()
        if verb in {"INSERT", "UPDATE", "DELETE", "REPLACE"}:
            writes.append(statement)

    engine = cast(Any, client.app).state.db_engine.sync_engine
    event.listen(engine, "before_cursor_execute", capture_statement)
    try:
        before = (_run(_chat_state(client, ids["chat"])), _run(_table_counts(client)))
        first = _compare_chat(
            client, ids["chat"], mode="new_message", message="달빛의 진실을 말해줘"
        )
        second = _compare_chat(
            client, ids["chat"], mode="new_message", message="달빛의 진실을 말해줘"
        )
        after = (_run(_chat_state(client, ids["chat"])), _run(_table_counts(client)))
    finally:
        event.remove(engine, "before_cursor_execute", capture_statement)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json() == second.json()
    assert before == after
    assert writes == []
    assert len(retrieve_calls) == 2, "exactly one retrieval per diagnostic call"

    report = first.json()
    assert report["situation"] == {
        "kind": "chat",
        "anchor_id": ids["chat"],
        "mode": "new_message",
        "memory_evaluation_time": None,
        "context_window": 4096,
        "max_tokens": 512,
        "safety_ratio": 0.08,
        "budget_source": "diagnostic_override",
        "entry_context_feature_enabled": False,
        "retrieval_policy_version": "entry-keyword-v1",
        "assembly_policy_version": "entry-prompt-block-v1",
        "projection_policy_version": "legacy-entry-equivalence-v1",
    }
    coverage = {
        row["projection"]["source_key"]: row for row in report["coverage"]["records"]
    }
    personality = coverage[f"character:{ids['character']}:personality:0"]
    assert personality["coverage_state"] == "equivalent"
    assert personality["eligible_exact_entry_ids"] == [personality_id]
    assert personality["projection"]["expected"]["normalized_length"] == len(
        "위기에도 침착하다."
    )
    glossary = coverage[f"glossary_term:{ids['glossary']}:definition:0"]
    assert glossary["coverage_state"] == "equivalent"
    runtime = {row["source_key"]: row for row in report["runtime"]["records"] if row["source_key"]}
    assert runtime[f"character:{ids['character']}:personality:0"]["runtime_state"] == "selection_mismatch"
    assert "stable_order_mismatch" in runtime[f"character:{ids['character']}:personality:0"]["diagnostic_codes"]
    assert "entry_context_feature_flag_off" in runtime[
        f"character:{ids['character']}:personality:0"
    ]["diagnostic_codes"]
    assert runtime[f"glossary_term:{ids['glossary']}:definition:0"]["runtime_state"] == "not_applicable"
    lore = runtime[f"lore_entry:{ids['lore']}:content:0"]
    assert "ignored_disabled_lorebook" in lore["diagnostic_codes"]
    assert lore["legacy"]["selected"] is True
    serialized = json.dumps(report, ensure_ascii=False).lower()
    assert "api_key" not in serialized
    assert "credential" not in serialized
    assert '"user_id"' not in serialized


async def _seed_chat_messages(client, chat_id: str) -> tuple[str, str]:  # noqa: ANN001
    sm = cast(Any, client.app).state.sessionmaker
    async with sm() as session:
        user = Message(
            chat_session_id=chat_id,
            user_id=_owner_id(),
            role="user",
            content="다시 말해줘",
            token_count=3,
            status="complete",
        )
        session.add(user)
        await session.flush()
        assistant = Message(
            chat_session_id=chat_id,
            user_id=_owner_id(),
            parent_message_id=user.id,
            role="assistant",
            content="첫 답변",
            token_count=2,
            status="complete",
            is_active=True,
        )
        session.add(assistant)
        await session.commit()
        return user.id, assistant.id


def test_regenerate_uses_ephemeral_omission_without_updating_messages(client) -> None:  # noqa: ANN001
    ids = _chat_fixture(client, "regen")
    _run(_seed_chat_messages(client, ids["chat"]))
    before = _run(_chat_state(client, ids["chat"]))
    response = _compare_chat(client, ids["chat"], mode="regenerate")
    after = _run(_chat_state(client, ids["chat"]))
    assert response.status_code == 200, response.text
    assert before == after
    assert response.json()["situation"]["mode"] == "regenerate"


def test_runtime_axes_allow_equivalent_and_missing_selection_mismatch(client) -> None:  # noqa: ANN001
    world = client.post("/api/v1/worlds", json={"name": "축세계"}).json()
    character = client.post(
        "/api/v1/characters",
        json={"name": "단일", "world_id": world["id"], "personality": "오직 하나"},
    ).json()
    chat = client.post(
        "/api/v1/chats", json={"character_id": character["id"]}
    ).json()
    _canon(
        client,
        scope_kind="character",
        scope_id=character["id"],
        subject_type="character",
        subject_id=character["id"],
        entry_type="character.identity",
        content="오직 하나",
    )
    report = _compare_chat(
        client, chat["id"], mode="new_message", message="계속"
    ).json()
    key = f"character:{character['id']}:personality:0"
    coverage = next(
        row for row in report["coverage"]["records"] if row["projection"]["source_key"] == key
    )
    runtime = next(row for row in report["runtime"]["records"] if row["source_key"] == key)
    assert coverage["coverage_state"] == "equivalent"
    assert runtime["runtime_state"] == "equivalent"

    missing_character = client.post(
        "/api/v1/characters", json={"name": "미싱", "personality": "Entry 없음"}
    ).json()
    missing_chat = client.post(
        "/api/v1/chats", json={"character_id": missing_character["id"]}
    ).json()
    missing_report = _compare_chat(
        client, missing_chat["id"], mode="new_message", message="계속"
    ).json()
    missing_key = f"character:{missing_character['id']}:personality:0"
    missing_coverage = next(
        row
        for row in missing_report["coverage"]["records"]
        if row["projection"]["source_key"] == missing_key
    )
    missing_runtime = next(
        row for row in missing_report["runtime"]["records"] if row["source_key"] == missing_key
    )
    assert missing_coverage["coverage_state"] == "missing_entry"
    assert missing_runtime["runtime_state"] == "selection_mismatch"


def test_duplicate_eligible_entries_are_coverage_ambiguous_and_runtime_multiplicity_mismatch(
    client,
) -> None:  # noqa: ANN001
    ids = _chat_fixture(client, "duplicate-entry")
    for _ in range(2):
        _canon(
            client,
            scope_kind="character",
            scope_id=ids["character"],
            subject_type="character",
            subject_id=ids["character"],
            entry_type="character.identity",
            content="위기에도 침착하다.",
        )

    report = _compare_chat(
        client, ids["chat"], mode="new_message", message="침착하게 답해줘"
    ).json()
    source_key = f"character:{ids['character']}:personality:0"
    coverage = next(
        row
        for row in report["coverage"]["records"]
        if row["projection"]["source_key"] == source_key
    )
    runtime = next(
        row for row in report["runtime"]["records"] if row["source_key"] == source_key
    )

    assert coverage["coverage_state"] == "ambiguous_match"
    assert len(coverage["eligible_exact_entry_ids"]) == 2
    assert runtime["runtime_state"] == "selection_mismatch"
    assert "runtime_occurrence_mismatch" in runtime["diagnostic_codes"]


def test_lore_equal_priority_order_is_reported_as_unsupported(client) -> None:  # noqa: ANN001
    ids = _chat_fixture(client, "lore-order")
    books = client.get(f"/api/v1/worlds/{ids['world']}/lorebooks").json()
    client.post(
        f"/api/v1/worlds/lorebooks/{books[0]['id']}/entries",
        json={
            "keywords": ["달빛"],
            "content": "동순위 두 번째 로어",
            "priority": 50,
            "enabled": True,
        },
    )
    report = _compare_chat(
        client, ids["chat"], mode="new_message", message="달빛"
    ).json()
    lore_records = [
        row
        for row in report["runtime"]["records"]
        if row["source_key"] and row["source_key"].startswith("lore_entry:")
    ]
    assert len(lore_records) == 2
    assert all(row["runtime_state"] == "unsupported_legacy_semantics" for row in lore_records)
    assert all(
        "legacy_equal_priority_order_unspecified" in row["diagnostic_codes"]
        for row in lore_records
    )


def test_lore_keyword_matching_remains_case_sensitive(client) -> None:  # noqa: ANN001
    ids = _chat_fixture(client, "lore-case")
    books = client.get(f"/api/v1/worlds/{ids['world']}/lorebooks").json()
    lore = client.post(
        f"/api/v1/worlds/lorebooks/{books[0]['id']}/entries",
        json={
            "keywords": ["Moon"],
            "content": "대소문자 구분 로어",
            "priority": 60,
            "enabled": True,
        },
    ).json()
    disabled_lore = client.post(
        f"/api/v1/worlds/lorebooks/{books[0]['id']}/entries",
        json={
            "keywords": ["moon"],
            "content": "비활성 로어",
            "priority": 70,
            "enabled": False,
        },
    ).json()
    report = _compare_chat(
        client, ids["chat"], mode="new_message", message="moon"
    ).json()
    runtime = next(
        row
        for row in report["runtime"]["records"]
        if row["source_key"] == f"lore_entry:{lore['id']}:content:0"
    )
    assert runtime["legacy"]["selected"] is False
    assert runtime["legacy"]["exclusion_code"] == "legacy_keyword_miss"
    assert "legacy_keyword_miss" in runtime["diagnostic_codes"]
    disabled_runtime = next(
        row
        for row in report["runtime"]["records"]
        if row["source_key"] == f"lore_entry:{disabled_lore['id']}:content:0"
    )
    assert disabled_runtime["legacy"]["selected"] is False
    assert disabled_runtime["legacy"]["exclusion_code"] == "legacy_disabled_entry"


def test_lore_shadow_uses_full_keywords_and_preserves_user_message_whitespace(
    client,
) -> None:  # noqa: ANN001
    ids = _chat_fixture(client, "lore-full-keywords")
    books = client.get(f"/api/v1/worlds/{ids['world']}/lorebooks").json()
    keywords = [f"miss-{index}" for index in range(10)] + [" needle "]
    lore = client.post(
        f"/api/v1/worlds/lorebooks/{books[0]['id']}/entries",
        json={
            "keywords": keywords,
            "content": "열한 번째 키워드로 선택되는 로어",
            "priority": 60,
            "enabled": True,
        },
    ).json()

    report = _compare_chat(
        client, ids["chat"], mode="new_message", message=" needle "
    ).json()
    runtime = next(
        row
        for row in report["runtime"]["records"]
        if row["source_key"] == f"lore_entry:{lore['id']}:content:0"
    )
    assert runtime["legacy"]["selected"] is True
    assert runtime["legacy"]["exclusion_code"] is None
    assert "legacy_keyword_miss" not in runtime["diagnostic_codes"]


@pytest.mark.parametrize(
    ("content", "override", "expected_code"),
    [
        ("가" * 400, {"context_window": 256, "max_tokens": 1, "safety_ratio": 0}, "entry_retrieval_budget_rejected"),
        ("가" * 251, {"context_window": 256, "max_tokens": 1, "safety_ratio": 0}, "entry_rendered_budget_rejected"),
        ("가" * 100, {"context_window": 512, "max_tokens": 1, "safety_ratio": 0}, "final_prompt_budget_drop"),
    ],
)
def test_runtime_keeps_retrieval_assembly_and_final_budget_exclusions_distinct(
    client, content, override, expected_code
) -> None:  # noqa: ANN001
    character = client.post(
        "/api/v1/characters", json={"name": "예산", "personality": content}
    ).json()
    chat = client.post(
        "/api/v1/chats", json={"character_id": character["id"]}
    ).json()
    _canon(
        client,
        scope_kind="character",
        scope_id=character["id"],
        subject_type="character",
        subject_id=character["id"],
        entry_type="character.identity",
        content=content,
    )
    message = "나" * 600 if expected_code == "final_prompt_budget_drop" else "계속"
    response = client.post(
        "/api/v1/entries/equivalence:compare",
        json={
            "chat": {
                "chat_id": chat["id"],
                "mode": "new_message",
                "user_message": message,
            },
            "budget_override": override,
        },
    )
    assert response.status_code == 200, response.text
    key = f"character:{character['id']}:personality:0"
    runtime = next(
        row for row in response.json()["runtime"]["records"] if row["source_key"] == key
    )
    assert expected_code in runtime["diagnostic_codes"]


def test_chat_validation_and_missing_anchor(client) -> None:  # noqa: ANN001
    private_prose = "오류 응답에 반사되면 안 되는 사용자 산문"
    both = client.post(
        "/api/v1/entries/equivalence:compare",
        json={
            "chat": {
                "chat_id": "x",
                "mode": "regenerate",
                "user_message": private_prose,
            },
            "novel": {"chapter_id": "y"},
            "budget_override": _OVERRIDE,
        },
    )
    assert both.status_code == 422
    assert private_prose not in both.text
    assert all(
        "input" not in error and "ctx" not in error
        for error in both.json()["error"]["details"]["errors"]
    )
    assert client.post(
        "/api/v1/entries/equivalence:compare", json={"budget_override": _OVERRIDE}
    ).status_code == 422
    assert client.post(
        "/api/v1/entries/equivalence:compare",
        json={
            "chat": {"chat_id": "x", "mode": "regenerate"},
            "budget_override": {"context_window": 1024},
        },
    ).status_code == 422
    assert client.post(
        "/api/v1/entries/equivalence:compare",
        json={
            "chat": {"chat_id": "x", "mode": "regenerate"},
            "budget_override": {
                "context_window": 256,
                "max_tokens": 512,
                "safety_ratio": 0,
            },
        },
    ).status_code == 422
    assert _compare_chat(client, "missing", mode="regenerate").status_code == 404
    assert _compare_chat(client, "x", mode="new_message").status_code == 422
    assert _compare_chat(client, "x", mode="regenerate", message="금지").status_code == 422
    assert _compare_chat(client, "x", mode="unsupported").status_code == 422
    assert client.post(
        "/api/v1/entries/equivalence:compare",
        json={
            "chat": {
                "chat_id": "x",
                "mode": "new_message",
                "user_message": "시각",
                "evaluation_time": "2026-01-01T00:00:00",
            },
            "budget_override": _OVERRIDE,
        },
    ).status_code == 422


def test_authentication_is_required_when_auth_is_enabled() -> None:
    from starlette.testclient import TestClient

    from app.config import get_settings as settings_dependency
    from app.main import create_app

    settings = get_settings().model_copy(update={"AUTH_ENABLED": True})
    app = create_app(settings)
    app.dependency_overrides[settings_dependency] = lambda: settings
    with TestClient(app) as secured:
        response = secured.post(
            "/api/v1/entries/equivalence:compare",
            json={
                "chat": {"chat_id": "anything", "mode": "regenerate"},
                "budget_override": _OVERRIDE,
            },
        )
    assert response.status_code == 401


async def _foreign_chat(client) -> str:  # noqa: ANN001
    sm = cast(Any, client.app).state.sessionmaker
    async with sm() as session:
        owner = User(email="foreign-equivalence@example.com", display_name="foreign")
        session.add(owner)
        await session.flush()
        character = Character(user_id=owner.id, name="foreign")
        session.add(character)
        await session.flush()
        chat = ChatSession(user_id=owner.id, character_id=character.id, title="foreign")
        session.add(chat)
        await session.commit()
        return chat.id


def test_foreign_chat_is_not_found_without_existence_leak(client) -> None:  # noqa: ANN001
    chat_id = _run(_foreign_chat(client))
    response = _compare_chat(client, chat_id, mode="regenerate")
    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Chat session not found"


async def _set_summaries_and_snapshot(
    client, summaries: dict[str, str], target_id: str
) -> tuple:  # noqa: ANN001
    sm = cast(Any, client.app).state.sessionmaker
    async with sm() as session:
        for chapter_id, summary in summaries.items():
            chapter = await session.get(Chapter, chapter_id)
            assert chapter is not None
            chapter.summary = summary
        await session.commit()
        target = await session.get(Chapter, target_id)
        assert target is not None
        count = int(
            (await session.execute(select(func.count(EditDiffCapture.id)))).scalar_one()
        )
        return (
            target.content_text,
            target.summary,
            target.version,
            target.content_doc,
            count,
        )


async def _chapter_snapshot(client, chapter_id: str) -> tuple:  # noqa: ANN001
    sm = cast(Any, client.app).state.sessionmaker
    async with sm() as session:
        chapter = await session.get(Chapter, chapter_id)
        assert chapter is not None
        count = int(
            (await session.execute(select(func.count(EditDiffCapture.id)))).scalar_one()
        )
        return (
            chapter.content_text,
            chapter.summary,
            chapter.version,
            chapter.content_doc,
            count,
        )


def test_novel_reports_prior_and_future_summary_without_mutation(client) -> None:  # noqa: ANN001
    world = client.post(
        "/api/v1/worlds",
        json={"name": "연대세계", "description": "연대 설명"},
    ).json()
    character = client.post(
        "/api/v1/characters",
        json={
            "name": "연대 주인공",
            "world_id": world["id"],
            "personality": "신중하다.",
            "speech_style": "낮게 말한다.",
        },
    ).json()
    work = client.post(
        "/api/v1/works",
        json={"title": "연대기", "world_id": world["id"]},
    ).json()
    assert client.post(
        f"/api/v1/works/{work['id']}/characters",
        json={"character_id": character["id"], "role_in_work": "주연"},
    ).status_code == 201
    chapters = [
        client.post(
            f"/api/v1/works/{work['id']}/chapters",
            json={"title": f"{index}화", "content_text": f"본문 {index}"},
        ).json()
        for index in range(1, 4)
    ]
    summaries = {
        chapters[0]["id"]: "첫 장에서 문을 열었다.",
        chapters[2]["id"]: "셋째 장에서 왕을 만났다.",
    }
    _run(_set_summaries_and_snapshot(client, summaries, chapters[1]["id"]))
    prior_entry = _canon(
        client,
        scope_kind="work",
        scope_id=work["id"],
        subject_type="chapter",
        subject_id=chapters[0]["id"],
        entry_type="story.summary",
        content=summaries[chapters[0]["id"]],
        data={"level": "chapter"},
        created_at_chapter_id=chapters[2]["id"],
    )
    future_entry = _canon(
        client,
        scope_kind="work",
        scope_id=work["id"],
        subject_type="chapter",
        subject_id=chapters[2]["id"],
        entry_type="story.summary",
        content=summaries[chapters[2]["id"]],
        data={"level": "chapter"},
        created_at_chapter_id=chapters[2]["id"],
    )
    unknown_entry = _canon(
        client,
        scope_kind="work",
        scope_id=work["id"],
        subject_type="work",
        subject_id=work["id"],
        entry_type="story.summary",
        content="위치를 특정할 수 없는 작품 요약",
        data={"level": "story"},
    )
    client.post(
        "/api/v1/model-configs",
        json={
            "provider": "openai",
            "model_name": "diagnostic-model",
            "max_tokens": 1024,
            "context_window": 8192,
            "is_default": True,
        },
    )
    before = _run(_chapter_snapshot(client, chapters[1]["id"]))
    response = client.post(
        "/api/v1/entries/equivalence:compare",
        json={
            "novel": {
                "chapter_id": chapters[1]["id"],
                "instruction": "문을 기억하며 이어 써라",
                "target_words": 50,
            }
        },
    )
    after = _run(_chapter_snapshot(client, chapters[1]["id"]))
    assert response.status_code == 200, response.text
    assert before == after
    report = response.json()
    assert report["situation"]["kind"] == "novel"
    assert report["situation"]["max_tokens"] == 80
    coverage = {
        row["projection"]["source_id"]: row for row in report["coverage"]["records"]
    }
    assert coverage[chapters[0]["id"]]["eligible_exact_entry_ids"] == [prior_entry]
    assert coverage[chapters[2]["id"]]["eligible_exact_entry_ids"] == [future_entry]
    future_runtime = next(
        row
        for row in report["runtime"]["records"]
        if row["source_key"] == f"chapter:{chapters[2]['id']}:summary:0"
    )
    assert future_runtime["legacy"]["selected"] is False
    assert future_runtime["entry"]["selected"] is True
    assert future_runtime["runtime_state"] == "selection_mismatch"
    assert "future_story_position_selected" in future_runtime["diagnostic_codes"]
    assert "database_timestamp_recency" in future_runtime["diagnostic_codes"]
    prior_runtime = next(
        row
        for row in report["runtime"]["records"]
        if row["source_key"] == f"chapter:{chapters[0]['id']}:summary:0"
    )
    assert prior_runtime["entry"]["selected"] is True
    assert "future_story_position_selected" in prior_runtime["diagnostic_codes"]
    character_runtime = next(
        row
        for row in report["runtime"]["records"]
        if row["source_key"] == f"character:{character['id']}:personality:0"
    )
    assert character_runtime["legacy"]["selected"] is True
    unknown_runtime = next(
        row for row in report["runtime"]["records"] if row["entry_id"] == unknown_entry
    )
    assert unknown_runtime["entry"]["selected"] is True
    assert "unknown_story_position" in unknown_runtime["diagnostic_codes"]


def test_novel_lore_shadow_uses_effective_default_instruction(client) -> None:  # noqa: ANN001
    world = client.post("/api/v1/worlds", json={"name": "기본지시세계"}).json()
    book = client.post(
        f"/api/v1/worlds/{world['id']}/lorebooks",
        json={"name": "기본 지시 로어", "enabled": True},
    ).json()
    lore = client.post(
        f"/api/v1/worlds/lorebooks/{book['id']}/entries",
        json={
            "keywords": ["자연스럽게"],
            "content": "기본 지시문에서 선택되는 로어",
            "priority": 50,
            "enabled": True,
        },
    ).json()
    work = client.post(
        "/api/v1/works", json={"title": "기본 지시 작품", "world_id": world["id"]}
    ).json()
    chapter = client.post(
        f"/api/v1/works/{work['id']}/chapters",
        json={"title": "1화", "content_text": "키워드 없는 본문"},
    ).json()

    response = client.post(
        "/api/v1/entries/equivalence:compare",
        json={
            "novel": {"chapter_id": chapter["id"], "instruction": ""},
            "budget_override": _OVERRIDE,
        },
    )
    assert response.status_code == 200, response.text
    runtime = next(
        row
        for row in response.json()["runtime"]["records"]
        if row["source_key"] == f"lore_entry:{lore['id']}:content:0"
    )
    assert runtime["legacy"]["selected"] is True
    assert runtime["legacy"]["exclusion_code"] is None


def test_novel_foreign_and_missing_chapter_are_not_found(client) -> None:  # noqa: ANN001
    response = client.post(
        "/api/v1/entries/equivalence:compare",
        json={"novel": {"chapter_id": "missing"}, "budget_override": _OVERRIDE},
    )
    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Chapter not found"

    async def seed_foreign() -> str:
        sm = cast(Any, client.app).state.sessionmaker
        async with sm() as session:
            owner = User(
                email="foreign-novel-equivalence@example.com", display_name="foreign"
            )
            session.add(owner)
            await session.flush()
            work = Work(user_id=owner.id, title="foreign")
            session.add(work)
            await session.flush()
            chapter = Chapter(
                work_id=work.id,
                user_id=owner.id,
                index=1,
                title="foreign",
                content_doc={},
                content_text="foreign",
            )
            session.add(chapter)
            await session.commit()
            return chapter.id

    foreign_id = _run(seed_foreign())
    foreign = client.post(
        "/api/v1/entries/equivalence:compare",
        json={"novel": {"chapter_id": foreign_id}, "budget_override": _OVERRIDE},
    )
    assert foreign.status_code == 404
    assert foreign.json()["error"]["message"] == "Chapter not found"

    work = client.post("/api/v1/works", json={"title": "삭제된 작품"}).json()
    chapter = client.post(
        f"/api/v1/works/{work['id']}/chapters",
        json={"title": "남은 장", "content_text": "내용"},
    ).json()
    assert client.delete(f"/api/v1/works/{work['id']}").status_code == 204
    deleted = client.post(
        "/api/v1/entries/equivalence:compare",
        json={"novel": {"chapter_id": chapter["id"]}, "budget_override": _OVERRIDE},
    )
    assert deleted.status_code == 404
    assert deleted.json()["error"]["message"] == "Chapter not found"


def test_final_budget_attribution_uses_source_identity_not_aggregate_substring(
    client,
) -> None:  # noqa: ANN001
    repeated = "겹침" * 30
    character = client.post(
        "/api/v1/characters",
        json={"name": repeated, "personality": repeated},
    ).json()
    chat = client.post(
        "/api/v1/chats", json={"character_id": character["id"]}
    ).json()
    _canon(
        client,
        scope_kind="character",
        scope_id=character["id"],
        subject_type="character",
        subject_id=character["id"],
        entry_type="character.identity",
        content=repeated,
    )

    response = client.post(
        "/api/v1/entries/equivalence:compare",
        json={
            "chat": {
                "chat_id": chat["id"],
                "mode": "new_message",
                "user_message": "나" * 300,
            },
            "budget_override": {
                "context_window": 512,
                "max_tokens": 1,
                "safety_ratio": 0,
            },
        },
    )
    assert response.status_code == 200, response.text
    source_key = f"character:{character['id']}:personality:0"
    runtime = next(
        row for row in response.json()["runtime"]["records"] if row["source_key"] == source_key
    )
    assert runtime["legacy"]["selected"] is False
    assert runtime["entry"]["selected"] is False
    assert runtime["runtime_state"] == "equivalent"
    assert "final_prompt_budget_drop" in runtime["diagnostic_codes"]


def test_novel_source_attribution_preserves_identity_for_identical_fields(
    client,
) -> None:  # noqa: ANN001
    repeated = "같은 원문"
    character = client.post(
        "/api/v1/characters",
        json={
            "name": repeated,
            "personality": repeated,
            "speech_style": repeated,
        },
    ).json()
    work = client.post("/api/v1/works", json={"title": "source span"}).json()
    assert client.post(
        f"/api/v1/works/{work['id']}/characters",
        json={"character_id": character["id"], "role_in_work": "주연"},
    ).status_code == 201
    chapter = client.post(
        f"/api/v1/works/{work['id']}/chapters",
        json={"title": "1화", "content_text": "본문"},
    ).json()
    for entry_type in ("character.identity", "character.voice"):
        _canon(
            client,
            scope_kind="character",
            scope_id=character["id"],
            subject_type="character",
            subject_id=character["id"],
            entry_type=entry_type,
            content=repeated,
        )

    response = client.post(
        "/api/v1/entries/equivalence:compare",
        json={
            "novel": {"chapter_id": chapter["id"], "target_words": 50},
            "budget_override": _OVERRIDE,
        },
    )
    assert response.status_code == 200, response.text
    runtime = {
        row["source_key"]: row
        for row in response.json()["runtime"]["records"]
        if row["source_key"]
    }
    for field_name in ("personality", "speech_style"):
        row = runtime[f"character:{character['id']}:{field_name}:0"]
        assert row["legacy"]["selected"] is True
        assert row["entry"]["selected"] is True


def test_not_applicable_entries_do_not_contaminate_applicable_runtime_order(
    client,
) -> None:  # noqa: ANN001
    world = client.post(
        "/api/v1/worlds",
        json={"name": "순서 세계", "description": "정상 설명", "races": ["선행 종족"]},
    ).json()
    character = client.post(
        "/api/v1/characters",
        json={"name": "순서 인물", "world_id": world["id"]},
    ).json()
    chat = client.post(
        "/api/v1/chats", json={"character_id": character["id"]}
    ).json()
    _canon(
        client,
        scope_kind="world",
        scope_id=world["id"],
        subject_type="world",
        subject_id=world["id"],
        entry_type="world.fact",
        content="정상 설명",
    )
    _canon(
        client,
        scope_kind="world",
        scope_id=world["id"],
        subject_type="world",
        subject_id=world["id"],
        entry_type="world.fact",
        content="종족: 선행 종족",
    )

    report = _compare_chat(
        client, chat["id"], mode="new_message", message="계속"
    ).json()
    description_key = f"world:{world['id']}:description:0"
    race_key = f"world:{world['id']}:races:0"
    runtime = {row["source_key"]: row for row in report["runtime"]["records"] if row["source_key"]}
    assert runtime[description_key]["runtime_state"] == "equivalent"
    assert "stable_order_mismatch" not in runtime[description_key]["diagnostic_codes"]
    assert runtime[race_key]["runtime_state"] == "not_applicable"


async def _seed_memory_competition(client, chat_id: str, base: datetime) -> None:  # noqa: ANN001
    sm = cast(Any, client.app).state.sessionmaker
    async with sm() as session:
        session.add_all(
            [
                Memory(
                    chat_session_id=chat_id,
                    user_id=_owner_id(),
                    kind="summary",
                    content="용문 기억",
                    version=1,
                    token_count=140,
                    created_at=base - timedelta(days=2),
                    updated_at=base - timedelta(days=2),
                ),
                Memory(
                    chat_session_id=chat_id,
                    user_id=_owner_id(),
                    kind="fact",
                    content="무관" * 115,
                    version=2,
                    token_count=140,
                    created_at=base,
                    updated_at=base,
                ),
            ]
        )
        await session.commit()


def test_memory_ranking_uses_explicit_evaluation_time_not_system_clock(
    client, monkeypatch
) -> None:  # noqa: ANN001
    world = client.post("/api/v1/worlds", json={"name": "기억 세계"}).json()
    character = client.post(
        "/api/v1/characters",
        json={"name": "기억 인물", "world_id": world["id"]},
    ).json()
    book = client.post(
        f"/api/v1/worlds/{world['id']}/lorebooks",
        json={"name": "기억 로어"},
    ).json()
    lore = client.post(
        f"/api/v1/worlds/lorebooks/{book['id']}/entries",
        json={"keywords": ["용문"], "content": "용문 규칙", "priority": 50},
    ).json()
    chat = client.post(
        "/api/v1/chats", json={"character_id": character["id"]}
    ).json()
    _canon(
        client,
        scope_kind="world",
        scope_id=world["id"],
        subject_type="world",
        subject_id=world["id"],
        entry_type="world.fact",
        content="용문 규칙",
    )
    base = datetime(2026, 1, 1, tzinfo=UTC)
    _run(_seed_memory_competition(client, chat["id"], base))

    def compare(evaluation_time: datetime):
        return client.post(
            "/api/v1/entries/equivalence:compare",
            json={
                "chat": {
                    "chat_id": chat["id"],
                    "mode": "new_message",
                    "user_message": "용문 " + "나" * 200,
                    "evaluation_time": evaluation_time.isoformat(),
                },
                "budget_override": {
                    "context_window": 512,
                    "max_tokens": 1,
                    "safety_ratio": 0,
                },
            },
        )

    class EarlySystemClock(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001, ANN206
            return base.astimezone(tz) if tz is not None else base.replace(tzinfo=None)

    class LateSystemClock(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001, ANN206
            value = base + timedelta(days=30)
            return value.astimezone(tz) if tz is not None else value.replace(tzinfo=None)

    monkeypatch.setattr(memory_engine_module, "datetime", EarlySystemClock)
    first = compare(base)
    monkeypatch.setattr(memory_engine_module, "datetime", LateSystemClock)
    repeated = compare(base)
    later_context = compare(base + timedelta(days=10))
    assert first.status_code == 200, first.text
    assert repeated.status_code == 200, repeated.text
    assert later_context.status_code == 200, later_context.text
    assert first.json() == repeated.json()

    source_key = f"lore_entry:{lore['id']}:content:0"
    early_runtime = next(
        row for row in first.json()["runtime"]["records"] if row["source_key"] == source_key
    )
    later_runtime = next(
        row
        for row in later_context.json()["runtime"]["records"]
        if row["source_key"] == source_key
    )
    assert early_runtime["legacy"]["selected"] is False
    assert later_runtime["legacy"]["selected"] is True


def test_memory_without_evaluation_time_reports_unsupported_semantics(client) -> None:  # noqa: ANN001
    character = client.post(
        "/api/v1/characters",
        json={"name": "평가 시각", "personality": "숨은 시각 없음"},
    ).json()
    chat = client.post(
        "/api/v1/chats", json={"character_id": character["id"]}
    ).json()
    _run(
        _seed_memory_competition(
            client, chat["id"], datetime(2026, 1, 1, tzinfo=UTC)
        )
    )

    response = _compare_chat(
        client, chat["id"], mode="new_message", message="용문"
    )
    assert response.status_code == 200, response.text
    source_key = f"character:{character['id']}:personality:0"
    runtime = next(
        row for row in response.json()["runtime"]["records"] if row["source_key"] == source_key
    )
    assert runtime["runtime_state"] == "unsupported_legacy_semantics"
    assert "memory_evaluation_time_required" in runtime["diagnostic_codes"]
    assert runtime["legacy"]["selected"] is False
    assert runtime["entry"]["final_prompt_selected"] is None


def test_production_memory_rank_wrapper_keeps_wall_clock_policy(monkeypatch) -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    candidates = [
        Memory(
            id="older-relevant",
            chat_session_id="chat",
            user_id="owner",
            kind="summary",
            content="용문 기억",
            token_count=1,
            created_at=base - timedelta(days=2),
            updated_at=base - timedelta(days=2),
        ),
        Memory(
            id="newer-irrelevant",
            chat_session_id="chat",
            user_id="owner",
            kind="fact",
            content="무관",
            token_count=1,
            created_at=base,
            updated_at=base,
        ),
    ]

    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN001, ANN206
            return base.astimezone(tz) if tz is not None else base.replace(tzinfo=None)

    monkeypatch.setattr(memory_engine_module, "datetime", FixedClock)
    engine = MemoryEngine(summarizer=cast(Any, None))
    assert engine._rank(candidates, "용문") == rank_memories(  # noqa: SLF001
        candidates, "용문", evaluation_time=base
    )


async def _seed_regenerate_timestamp_tie(client, chat_id: str) -> None:  # noqa: ANN001
    sm = cast(Any, client.app).state.sessionmaker
    tied = datetime(2026, 2, 1, tzinfo=UTC)
    async with sm() as session:
        user = Message(
            chat_session_id=chat_id,
            user_id=_owner_id(),
            role="user",
            content="동률 재생성",
            token_count=5,
            status="complete",
            created_at=tied,
            updated_at=tied,
        )
        session.add(user)
        await session.flush()
        session.add_all(
            [
                Message(
                    chat_session_id=chat_id,
                    user_id=_owner_id(),
                    parent_message_id=user.id,
                    role="assistant",
                    content="동률 답변 A",
                    token_count=5,
                    status="complete",
                    created_at=tied,
                    updated_at=tied,
                ),
                Message(
                    chat_session_id=chat_id,
                    user_id=_owner_id(),
                    parent_message_id=user.id,
                    role="assistant",
                    content="동률 답변 B",
                    token_count=5,
                    status="complete",
                    created_at=tied,
                    updated_at=tied,
                ),
            ]
        )
        await session.commit()


def test_regenerate_timestamp_tie_is_reported_as_unsupported(client) -> None:  # noqa: ANN001
    character = client.post(
        "/api/v1/characters",
        json={"name": "동률 인물", "personality": "동률 성격"},
    ).json()
    chat = client.post(
        "/api/v1/chats", json={"character_id": character["id"]}
    ).json()
    _run(_seed_regenerate_timestamp_tie(client, chat["id"]))

    response = _compare_chat(client, chat["id"], mode="regenerate")
    assert response.status_code == 200, response.text
    source_key = f"character:{character['id']}:personality:0"
    runtime = next(
        row for row in response.json()["runtime"]["records"] if row["source_key"] == source_key
    )
    assert runtime["runtime_state"] == "unsupported_legacy_semantics"
    assert runtime["legacy"]["selected"] is False
    assert runtime["entry"]["selected"] is False
    assert "regenerate_assistant_timestamp_tie" in runtime["diagnostic_codes"]


async def _seed_regenerate_user_timestamp_tie(client, chat_id: str) -> None:  # noqa: ANN001
    sm = cast(Any, client.app).state.sessionmaker
    tied = datetime(2026, 3, 1, tzinfo=UTC)
    async with sm() as session:
        users = [
            Message(
                chat_session_id=chat_id,
                user_id=_owner_id(),
                role="user",
                content=f"동률 사용자 {suffix}",
                token_count=5,
                status="complete",
                created_at=tied,
                updated_at=tied,
            )
            for suffix in ("A", "B")
        ]
        session.add_all(users)
        await session.flush()
        session.add(
            Message(
                chat_session_id=chat_id,
                user_id=_owner_id(),
                parent_message_id=users[0].id,
                role="assistant",
                content="유일한 답변",
                token_count=5,
                status="complete",
                created_at=tied + timedelta(seconds=1),
                updated_at=tied + timedelta(seconds=1),
            )
        )
        await session.commit()


def test_regenerate_user_timestamp_tie_is_also_unsupported(client) -> None:  # noqa: ANN001
    character = client.post(
        "/api/v1/characters",
        json={"name": "사용자 동률", "personality": "사용자 동률 성격"},
    ).json()
    chat = client.post(
        "/api/v1/chats", json={"character_id": character["id"]}
    ).json()
    _run(_seed_regenerate_user_timestamp_tie(client, chat["id"]))

    response = _compare_chat(client, chat["id"], mode="regenerate")
    assert response.status_code == 200, response.text
    source_key = f"character:{character['id']}:personality:0"
    runtime = next(
        row for row in response.json()["runtime"]["records"] if row["source_key"] == source_key
    )
    assert runtime["runtime_state"] == "unsupported_legacy_semantics"
    assert "regenerate_user_timestamp_tie" in runtime["diagnostic_codes"]


def test_future_summary_codes_distinguish_selected_and_not_selected_entries(
    client,
) -> None:  # noqa: ANN001
    work = client.post("/api/v1/works", json={"title": "미래 선택 구분"}).json()
    chapters = [
        client.post(
            f"/api/v1/works/{work['id']}/chapters",
            json={"title": f"{index}화", "content_text": "현재 본문"},
        ).json()
        for index in range(1, 5)
    ]
    selected_id = _canon(
        client,
        scope_kind="work",
        scope_id=work["id"],
        subject_type="chapter",
        subject_id=chapters[3]["id"],
        entry_type="story.summary",
        content="선택되는 미래 요약",
        data={"level": "chapter"},
    )
    not_selected_id = _canon(
        client,
        scope_kind="work",
        scope_id=work["id"],
        subject_type="chapter",
        subject_id=chapters[2]["id"],
        entry_type="story.summary",
        content="탈락하는 미래 요약" * 80,
        data={"level": "chapter"},
    )

    response = client.post(
        "/api/v1/entries/equivalence:compare",
        json={
            "novel": {"chapter_id": chapters[1]["id"], "target_words": 50},
            "budget_override": {
                "context_window": 512,
                "max_tokens": 1,
                "safety_ratio": 0,
            },
        },
    )
    assert response.status_code == 200, response.text
    entry_only = {row["entry_id"]: row for row in response.json()["entry_only"]}
    assert entry_only[selected_id]["runtime_selected"] is True
    assert "future_story_position_selected" in entry_only[selected_id]["diagnostic_codes"]
    assert entry_only[not_selected_id]["runtime_selected"] is False
    assert "future_story_position_selected" not in entry_only[not_selected_id]["diagnostic_codes"]
    assert "future_story_position_not_selected" in entry_only[not_selected_id]["diagnostic_codes"]


def test_zero_length_resolved_legacy_source_is_not_runtime_selected(client) -> None:  # noqa: ANN001
    unresolved = "{{missing.variable}}"
    world = client.post(
        "/api/v1/worlds",
        json={"name": "빈 해석 세계", "description": unresolved},
    ).json()
    character = client.post(
        "/api/v1/characters",
        json={
            "name": "빈 해석 인물",
            "world_id": world["id"],
            "personality": unresolved,
        },
    ).json()
    chat = client.post(
        "/api/v1/chats", json={"character_id": character["id"]}
    ).json()
    entry_id = _canon(
        client,
        scope_kind="character",
        scope_id=character["id"],
        subject_type="character",
        subject_id=character["id"],
        entry_type="character.identity",
        content=unresolved,
    )
    world_entry_id = _canon(
        client,
        scope_kind="world",
        scope_id=world["id"],
        subject_type="world",
        subject_id=world["id"],
        entry_type="world.fact",
        content=unresolved,
    )

    response = _compare_chat(
        client, chat["id"], mode="new_message", message="계속"
    )
    assert response.status_code == 200, response.text
    source_key = f"character:{character['id']}:personality:0"
    coverage = next(
        row
        for row in response.json()["coverage"]["records"]
        if row["projection"]["source_key"] == source_key
    )
    runtime = next(
        row
        for row in response.json()["runtime"]["records"]
        if row["source_key"] == source_key
    )
    assert coverage["eligible_exact_entry_ids"] == [entry_id]
    assert runtime["legacy"]["selected"] is False
    assert runtime["entry"]["selected"] is True
    assert runtime["runtime_state"] == "selection_mismatch"
    assert runtime["legacy"]["exclusion_code"] == "legacy_resolved_payload_empty"
    assert "legacy_resolved_payload_empty" in runtime["diagnostic_codes"]
    assert "final_prompt_budget_drop" not in runtime["diagnostic_codes"]

    world_source_key = f"world:{world['id']}:description:0"
    world_coverage = next(
        row
        for row in response.json()["coverage"]["records"]
        if row["projection"]["source_key"] == world_source_key
    )
    world_runtime = next(
        row
        for row in response.json()["runtime"]["records"]
        if row["source_key"] == world_source_key
    )
    assert world_coverage["eligible_exact_entry_ids"] == [world_entry_id]
    assert world_runtime["legacy"]["selected"] is False
    assert world_runtime["entry"]["selected"] is True
    assert world_runtime["runtime_state"] == "selection_mismatch"
    assert world_runtime["legacy"]["exclusion_code"] == "legacy_resolved_payload_empty"


@pytest.mark.parametrize("entry_matches_rendered_order", [True, False])
def test_novel_multi_character_order_uses_rendered_source_spans(
    client, entry_matches_rendered_order: bool
) -> None:  # noqa: ANN001
    characters = [
        client.post(
            "/api/v1/characters",
            json={"name": name, "personality": personality},
        ).json()
        for name, personality in (
            ("렌더 첫 인물", "렌더 첫 성격"),
            ("렌더 둘째 인물", "렌더 둘째 성격"),
        )
    ]
    rendered_first, rendered_second = sorted(
        characters, key=lambda item: item["id"], reverse=True
    )
    assert rendered_first["id"] > rendered_second["id"]

    work = client.post("/api/v1/works", json={"title": "실제 렌더 순서"}).json()
    for character in (rendered_first, rendered_second):
        response = client.post(
            f"/api/v1/works/{work['id']}/characters",
            json={"character_id": character["id"], "role_in_work": "주연"},
        )
        assert response.status_code == 201, response.text
    chapter = client.post(
        f"/api/v1/works/{work['id']}/chapters",
        json={"title": "1화", "content_text": "현재 본문"},
    ).json()

    first_priority, second_priority = (
        (100, 0) if entry_matches_rendered_order else (0, 100)
    )
    for character, priority in (
        (rendered_first, first_priority),
        (rendered_second, second_priority),
    ):
        _canon(
            client,
            scope_kind="character",
            scope_id=character["id"],
            subject_type="character",
            subject_id=character["id"],
            entry_type="character.identity",
            content=character["personality"],
            priority=priority,
        )

    response = client.post(
        "/api/v1/entries/equivalence:compare",
        json={
            "novel": {"chapter_id": chapter["id"], "target_words": 50},
            "budget_override": _OVERRIDE,
        },
    )
    assert response.status_code == 200, response.text
    source_keys = {
        f"character:{rendered_first['id']}:personality:0",
        f"character:{rendered_second['id']}:personality:0",
    }
    runtime = [
        row
        for row in response.json()["runtime"]["records"]
        if row["source_key"] in source_keys
    ]
    assert all(row["legacy"]["selected"] is True for row in runtime)
    assert all(row["entry"]["selected"] is True for row in runtime)
    if entry_matches_rendered_order:
        assert all(row["runtime_state"] == "equivalent" for row in runtime)
        assert all(
            "stable_order_mismatch" not in row["diagnostic_codes"] for row in runtime
        )
    else:
        assert all(row["runtime_state"] == "selection_mismatch" for row in runtime)
        assert all(
            "stable_order_mismatch" in row["diagnostic_codes"] for row in runtime
        )


def test_exact_future_summary_rejected_by_retrieval_has_not_selected_chronology(
    client,
) -> None:  # noqa: ANN001
    work = client.post("/api/v1/works", json={"title": "미래 exact 탈락"}).json()
    chapters = [
        client.post(
            f"/api/v1/works/{work['id']}/chapters",
            json={"title": f"{index}화", "content_text": "현재 본문"},
        ).json()
        for index in range(1, 3)
    ]
    long_summary = "선택 예산을 넘는 미래 요약 " * 300
    _run(
        _set_summaries_and_snapshot(
            client, {chapters[1]["id"]: long_summary}, chapters[0]["id"]
        )
    )
    entry_id = _canon(
        client,
        scope_kind="work",
        scope_id=work["id"],
        subject_type="chapter",
        subject_id=chapters[1]["id"],
        entry_type="story.summary",
        content=long_summary,
        data={"level": "chapter"},
    )

    response = client.post(
        "/api/v1/entries/equivalence:compare",
        json={
            "novel": {"chapter_id": chapters[0]["id"], "target_words": 50},
            "budget_override": {
                "context_window": 512,
                "max_tokens": 1,
                "safety_ratio": 0,
            },
        },
    )
    assert response.status_code == 200, response.text
    source_key = f"chapter:{chapters[1]['id']}:summary:0"
    runtime = next(
        row
        for row in response.json()["runtime"]["records"]
        if row["source_key"] == source_key
    )
    assert runtime["entry"]["trace_ids"] == [entry_id]
    assert runtime["entry"]["retrieval_selected"] is False
    assert runtime["entry"]["selected"] is False
    assert runtime["entry"]["final_prompt_selected"] is False
    assert runtime["entry"]["exclusion_code"] == "entry_retrieval_budget_rejected"
    assert "entry_retrieval_budget_rejected" in runtime["diagnostic_codes"]
    assert "database_timestamp_recency" in runtime["diagnostic_codes"]
    assert "future_story_position_not_selected" in runtime["diagnostic_codes"]
    assert "future_story_position_selected" not in runtime["diagnostic_codes"]
