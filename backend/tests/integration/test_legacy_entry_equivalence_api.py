"""P1-8 owner-safe, provider-free, non-mutating diagnostic API tests."""
from __future__ import annotations

import asyncio
import json
from typing import Any, cast

import pytest
from sqlalchemy import event, func, select

from app.config import get_settings
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
) -> str:
    payload: dict[str, object] = {
        "scope_kind": scope_kind,
        "scope_id": scope_id,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "type": entry_type,
        "content": content,
        "data": data or {},
        "priority": 80,
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
