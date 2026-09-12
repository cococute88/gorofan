"""AOS-3 direct Gemini production path through the existing Novel endpoint."""
from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import partial
from typing import Any, cast
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select
from starlette.testclient import TestClient

from app.adapters.gemini import GeminiAdapter
from app.config import FEATURE_ENTRY_STORE_CONTEXT, get_settings
from app.core.security import encrypt_secret
from app.engines.novel.engine import NovelEngine
from app.models.ai_config import ModelConfig, ProviderCredential
from app.models.chat import Memory
from app.models.edit_diff import EditDiffCapture
from app.models.entry import Entry
from app.models.novel import Chapter
from app.models.user import User
from app.services.novel_service import NovelService
from app.services.provider_resolve import resolve_provider_request

OWNER_SECRET = "owner-gemini-secret"
FOREIGN_SECRET = "foreign-gemini-secret-must-not-leak"
MEMORY_SENTINEL = "PRIVATE_CHAT_MEMORY_MUST_NOT_REACH_NOVEL"
FUTURE_SENTINEL = "FUTURE_CHAPTER_SUMMARY_MUST_NOT_LEAK"


def _sse(*events: dict) -> str:
    return "".join(
        f"data: {json.dumps(event, ensure_ascii=False)}\n\n" for event in events
    )


def _text_event(text: str, *, finish_reason: str | None = None) -> dict:
    candidate: dict[str, object] = {
        "index": 0,
        "content": {"role": "model", "parts": [{"text": text}]},
    }
    if finish_reason is not None:
        candidate["finishReason"] = finish_reason
    return {"candidates": [candidate]}


@pytest.fixture()
def gemini_client() -> Iterator[TestClient]:
    from app.main import create_app

    settings = get_settings().model_copy(
        update={"FEATURES": {FEATURE_ENTRY_STORE_CONTEXT: True}}
    )
    manager = TestClient(create_app(settings))
    client = manager.__enter__()
    try:
        yield client
    finally:
        manager.__exit__(None, None, None)


def _run(client: TestClient, function, *args):  # noqa: ANN001, ANN202
    assert client.portal is not None
    sessionmaker = cast(Any, client.app).state.sessionmaker
    return client.portal.call(partial(function, sessionmaker, *args))


async def _seed_generation_context(
    sessionmaker,
    first_chapter_id: str,
    future_chapter_id: str,
    chat_id: str,
    work_id: str,
    character_ids: tuple[str, str],
) -> None:
    settings = get_settings()
    foreign_user_id = str(uuid4())
    foreign_credential = ProviderCredential(
        user_id=foreign_user_id,
        provider="gemini",
        api_key_enc=encrypt_secret(settings, FOREIGN_SECRET),
        label="foreign sentinel",
    )
    async with sessionmaker() as session:
        first = await session.get(Chapter, first_chapter_id)
        future = await session.get(Chapter, future_chapter_id)
        assert first is not None and future is not None
        first.summary = "PRIOR_CHRONOLOGY_SENTINEL 먼저 열린 문을 통과했다."
        future.summary = FUTURE_SENTINEL
        foreign_user = User(
            id=foreign_user_id,
            email=f"foreign-gemini-{uuid4()}@example.com",
            display_name="foreign",
        )
        session.add(foreign_user)
        await session.flush()
        session.add(foreign_credential)
        await session.flush()
        session.add(
            ModelConfig(
                user_id=foreign_user_id,
                provider="gemini",
                model_name="gemini-3.8-flash",
                credential_id=foreign_credential.id,
                label="foreign default",
                purpose="novel",
                temperature=0.1,
                max_tokens=10,
                context_window=1_048_576,
                is_default=True,
            )
        )
        session.add(
            Memory(
                chat_session_id=chat_id,
                user_id=settings.DEFAULT_USER_ID,
                kind="fact",
                content=MEMORY_SENTINEL,
            )
        )
        pair = sorted(character_ids)
        session.add(
            Entry(
                user_id=settings.DEFAULT_USER_ID,
                scope_kind="work",
                scope_id=work_id,
                subject_type="character-pair",
                subject_id="|".join(pair),
                subject_data={"character_ids": pair},
                type="relationship.state",
                status="canon",
                content="RELATIONSHIP_SENTINEL 두 인물은 서로를 경계한다.",
                data={},
                provenance={
                    "source_kind": "user",
                    "capture_method": "human-authored",
                    "producer": "aos-3-test",
                },
                priority=100,
                created_at_chapter_id=first_chapter_id,
                accepted_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        await session.commit()


async def _credential_ciphertext(sessionmaker, credential_id: str) -> str:
    async with sessionmaker() as session:
        credential = await session.get(ProviderCredential, credential_id)
        assert credential is not None
        return credential.api_key_enc


async def _captures(sessionmaker, chapter_id: str) -> list[EditDiffCapture]:
    async with sessionmaker() as session:
        rows = await session.execute(
            select(EditDiffCapture)
            .where(EditDiffCapture.chapter_id == chapter_id)
            .order_by(EditDiffCapture.sequence)
        )
        return list(rows.scalars().all())


async def _capture_count(sessionmaker, chapter_id: str) -> int:
    async with sessionmaker() as session:
        value = await session.scalar(
            select(func.count())
            .select_from(EditDiffCapture)
            .where(EditDiffCapture.chapter_id == chapter_id)
        )
        return int(value or 0)


async def _seed_foreign_credential(sessionmaker) -> str:
    settings = get_settings()
    foreign_user_id = str(uuid4())
    credential = ProviderCredential(
        user_id=foreign_user_id,
        provider="gemini",
        api_key_enc=encrypt_secret(settings, FOREIGN_SECRET),
        label="foreign-only",
    )
    async with sessionmaker() as session:
        foreign_user = User(
            id=foreign_user_id,
            email=f"foreign-credential-{uuid4()}@example.com",
            display_name="foreign",
        )
        session.add(foreign_user)
        await session.flush()
        session.add(credential)
        await session.commit()
        return credential.id


async def _seed_and_resolve_oversize_config(
    sessionmaker,
    settings,
    registry,
) -> tuple[int, int]:
    config = ModelConfig(
        user_id=settings.DEFAULT_USER_ID,
        provider="gemini",
        model_name="gemini-3.8-flash",
        label="legacy oversize",
        purpose="novel",
        temperature=0.7,
        max_tokens=70_000,
        context_window=1_048_576,
        is_default=False,
    )
    async with sessionmaker() as session:
        session.add(config)
        await session.commit()
        request = await resolve_provider_request(
            session,
            settings,
            registry,
            user_id=settings.DEFAULT_USER_ID,
            model_config_id=config.id,
            purpose="novel",
        )
        return request.max_tokens, request.context_window


def _create_gemini_config(
    client: TestClient,
    *,
    credential_id: str | None,
    max_tokens: int = 1024,
) -> dict:
    response = client.post(
        "/api/v1/model-configs",
        json={
            "provider": "gemini",
            "model_name": "gemini-3.8-flash",
            "credential_id": credential_id,
            "label": "AOS-3 Gemini",
            "purpose": "novel",
            "temperature": 0.7,
            "max_tokens": max_tokens,
            "context_window": 1_048_576,
            "is_default": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _setup_work(client: TestClient) -> tuple[str, str, str, str, tuple[str, str]]:
    world = client.post(
        "/api/v1/worlds",
        json={"name": "설원", "description": "WORLD_SENTINEL 긴 겨울의 땅"},
    ).json()
    work = client.post(
        "/api/v1/works",
        json={
            "title": "겨울 궁전",
            "synopsis": "몰락한 공녀의 귀환",
            "genre": "로맨스 판타지",
            "world_id": world["id"],
        },
    ).json()
    characters = []
    for name, personality in (("하린", "CHARACTER_ONE 침착함"), ("준", "CHARACTER_TWO 냉정함")):
        character = client.post(
            "/api/v1/characters",
            json={"name": name, "personality": personality},
        ).json()
        characters.append(character)
        linked = client.post(
            f"/api/v1/works/{work['id']}/characters",
            json={"character_id": character["id"], "role_in_work": "주연"},
        )
        assert linked.status_code == 201, linked.text
    chapters = []
    for title, content in (
        ("과거", "첫 장의 본문"),
        ("현재", "CURRENT_CHAPTER_SENTINEL 눈보라 속에서 문이 열렸다."),
        ("미래", "아직 일어나지 않은 본문"),
    ):
        chapters.append(
            client.post(
                f"/api/v1/works/{work['id']}/chapters",
                json={"title": title, "content_text": content},
            ).json()
        )
    return (
        work["id"],
        chapters[0]["id"],
        chapters[1]["id"],
        chapters[2]["id"],
        (characters[0]["id"], characters[1]["id"]),
    )


def _chapter(client: TestClient, work_id: str, chapter_id: str) -> dict:
    chapters = client.get(f"/api/v1/works/{work_id}/chapters").json()
    return next(item for item in chapters if item["id"] == chapter_id)


def _disable_retries(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    registry = cast(Any, client.app).state.registry
    original = registry.stream_with_resilience

    async def no_retry(prompt, req, max_retries=2):  # noqa: ANN001, ANN202, ARG001
        async for token in original(prompt, req, max_retries=0):
            yield token

    monkeypatch.setattr(registry, "stream_with_resilience", no_retry)


def test_aos_preparation_reaches_existing_gemini_once_and_appends_once(
    gemini_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[httpx.Request] = []
    prepared_calls = 0
    append_calls = 0
    assembled_prompts = []
    original_prepare = NovelService._prepare_continue_context
    original_append = NovelService._append_chapter
    original_assemble = NovelEngine.assemble_continue

    async def counted_prepare(self, *args, **kwargs):  # noqa: ANN001, ANN202
        nonlocal prepared_calls
        prepared_calls += 1
        return await original_prepare(self, *args, **kwargs)

    async def counted_append(self, *args, **kwargs):  # noqa: ANN001, ANN202
        nonlocal append_calls
        append_calls += 1
        return await original_append(self, *args, **kwargs)

    def counted_assemble(self, *args, **kwargs):  # noqa: ANN001, ANN202
        prompt = original_assemble(self, *args, **kwargs)
        assembled_prompts.append(prompt)
        return prompt

    monkeypatch.setattr(NovelService, "_prepare_continue_context", counted_prepare)
    monkeypatch.setattr(NovelService, "_append_chapter", counted_append)
    monkeypatch.setattr(NovelEngine, "assemble_continue", counted_assemble)

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            content=_sse(
                _text_event("새 문장이 "),
                _text_event("이어졌다. 😊", finish_reason="STOP"),
            ).encode("utf-8"),
            headers={"Content-Type": "text/event-stream; charset=utf-8"},
        )

    transport = httpx.MockTransport(handler)
    cast(Any, gemini_client.app).state.registry.register(
        "gemini", lambda: GeminiAdapter(transport=transport)
    )
    credential = gemini_client.post(
        "/api/v1/credentials",
        json={"provider": "gemini", "api_key": OWNER_SECRET, "label": "owner"},
    )
    assert credential.status_code == 201, credential.text
    credential_id = credential.json()["id"]
    _create_gemini_config(gemini_client, credential_id=credential_id)
    work_id, first_id, target_id, future_id, character_ids = _setup_work(gemini_client)
    chat = gemini_client.post(
        "/api/v1/chats", json={"character_id": character_ids[0]}
    ).json()
    _run(
        gemini_client,
        _seed_generation_context,
        first_id,
        future_id,
        chat["id"],
        work_id,
        character_ids,
    )
    before = _chapter(gemini_client, work_id, target_id)
    assert _run(gemini_client, _capture_count, target_id) == 0

    response = gemini_client.post(
        f"/api/v1/works/chapters/{target_id}/continue",
        json={
            "instruction": "FREEFORM_SENTINEL 감정선을 천천히 진행해줘.",
            "target_words": 100,
            "scene": {
                "goal": "SCENE_GOAL_SENTINEL 결계 이상을 알아차린다.",
                "beats": ["SCENE_BEAT_ONE", "SCENE_BEAT_TWO"],
                "must_include": ["SCENE_INCLUDE_SENTINEL 은빛 표식"],
                "must_avoid": ["SCENE_AVOID_SENTINEL 갑작스러운 악역"],
            },
        },
    )

    assert response.status_code == 200, response.text
    assert response.text.count("event: token") == 2
    assert response.text.count("event: done") == 1
    assert "event: error" not in response.text
    assert response.text.index("event: token") < response.text.index("event: done")
    assert len(captured) == 1
    assert prepared_calls == 1
    assert append_calls == 1
    assert len(assembled_prompts) == 1

    outgoing = captured[0]
    assert outgoing.headers["x-goog-api-key"] == OWNER_SECRET
    assert OWNER_SECRET not in str(outgoing.url)
    assert FOREIGN_SECRET not in str(outgoing.url)
    assert outgoing.url.params.get("key") is None
    payload = json.loads(outgoing.content)
    payload_text = json.dumps(payload, ensure_ascii=False)
    assert payload["generationConfig"] == {
        "temperature": 0.7,
        "maxOutputTokens": 160,
    }
    for sentinel in (
        "CHARACTER_ONE",
        "CHARACTER_TWO",
        "WORLD_SENTINEL",
        "RELATIONSHIP_SENTINEL",
        "PRIOR_CHRONOLOGY_SENTINEL",
        "CURRENT_CHAPTER_SENTINEL",
        "FREEFORM_SENTINEL",
        "SCENE_GOAL_SENTINEL",
        "SCENE_BEAT_ONE",
        "SCENE_BEAT_TWO",
        "SCENE_INCLUDE_SENTINEL",
        "SCENE_AVOID_SENTINEL",
    ):
        assert payload_text.count(sentinel) == 1
    assert MEMORY_SENTINEL not in payload_text
    assert FUTURE_SENTINEL not in payload_text
    assert FOREIGN_SECRET not in payload_text
    prompt = assembled_prompts[0]
    safety_reservation = int(1_048_576 * 0.08)
    assert prompt.trace["context_window"] == 1_048_576
    assert prompt.trace["max_tokens"] == 160
    assert prompt.token_count + 160 + safety_reservation <= 1_048_576

    after = _chapter(gemini_client, work_id, target_id)
    assert after["version"] == before["version"] + 1
    assert after["content_text"] == (
        before["content_text"] + "\n\n새 문장이 이어졌다. 😊"
    )
    captures = _run(gemini_client, _captures, target_id)
    assert len(captures) == 1
    assert captures[0].before_text == "새 문장이 이어졌다. 😊"
    assert captures[0].context["provider"] == "gemini"
    assert captures[0].context["model"] == "gemini-3.8-flash"
    assert captures[0].context["partial_stream"] is False

    ciphertext = _run(gemini_client, _credential_ciphertext, credential_id)
    assert ciphertext != OWNER_SECRET
    assert OWNER_SECRET not in ciphertext
    listed = gemini_client.get("/api/v1/credentials").text
    assert OWNER_SECRET not in listed


def test_gemini_legacy_request_without_scene_still_streams_and_appends(
    gemini_client: TestClient,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            text=_sse(_text_event("레거시 계속", finish_reason="STOP")),
        )

    cast(Any, gemini_client.app).state.registry.register(
        "gemini", lambda: GeminiAdapter(transport=httpx.MockTransport(handler))
    )
    credential = gemini_client.post(
        "/api/v1/credentials",
        json={"provider": "gemini", "api_key": OWNER_SECRET, "label": "legacy"},
    ).json()
    _create_gemini_config(gemini_client, credential_id=credential["id"])
    work_id, _first, target_id, _future, _characters = _setup_work(gemini_client)
    before = _chapter(gemini_client, work_id, target_id)

    response = gemini_client.post(
        f"/api/v1/works/chapters/{target_id}/continue",
        json={"instruction": "LEGACY_INSTRUCTION_SENTINEL 계속", "target_words": 50},
    )

    assert "event: token" in response.text
    assert "event: done" in response.text
    assert len(requests) == 1
    assert json.loads(requests[0].content).__str__().count("LEGACY_INSTRUCTION_SENTINEL") == 1
    after = _chapter(gemini_client, work_id, target_id)
    assert after["version"] == before["version"] + 1
    assert after["content_text"].endswith("레거시 계속")


@pytest.mark.parametrize(
    ("status", "expected_code"),
    [(429, "PROVIDER_RATE_LIMIT"), (503, "PROVIDER_ERROR")],
)
def test_gemini_provider_failure_is_terminal_sse_without_chapter_write(
    gemini_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    expected_code: str,
) -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status, json={"error": {"message": FOREIGN_SECRET}})

    cast(Any, gemini_client.app).state.registry.register(
        "gemini", lambda: GeminiAdapter(transport=httpx.MockTransport(handler))
    )
    _disable_retries(gemini_client, monkeypatch)
    credential = gemini_client.post(
        "/api/v1/credentials",
        json={"provider": "gemini", "api_key": OWNER_SECRET, "label": "error"},
    ).json()
    _create_gemini_config(gemini_client, credential_id=credential["id"])
    work_id, _first, target_id, _future, _characters = _setup_work(gemini_client)
    before = _chapter(gemini_client, work_id, target_id)

    response = gemini_client.post(
        f"/api/v1/works/chapters/{target_id}/continue",
        json={"instruction": "실패 경로", "target_words": 50},
    )

    assert attempts == 1
    assert response.text.count("event: error") == 1
    assert f'"code": "{expected_code}"' in response.text
    assert "event: token" not in response.text
    assert "event: done" not in response.text
    assert FOREIGN_SECRET not in response.text
    assert _chapter(gemini_client, work_id, target_id) == before
    assert _run(gemini_client, _capture_count, target_id) == 0


@pytest.mark.parametrize("credential_kind", ["missing", "foreign"])
def test_missing_or_foreign_gemini_credential_never_attempts_network_or_writes(
    gemini_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    credential_kind: str,
) -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, text=_sse(_text_event("금지")))

    cast(Any, gemini_client.app).state.registry.register(
        "gemini", lambda: GeminiAdapter(transport=httpx.MockTransport(handler))
    )
    _disable_retries(gemini_client, monkeypatch)
    credential_id = (
        None
        if credential_kind == "missing"
        else _run(gemini_client, _seed_foreign_credential)
    )
    _create_gemini_config(gemini_client, credential_id=credential_id)
    work_id, _first, target_id, _future, _characters = _setup_work(gemini_client)
    before = _chapter(gemini_client, work_id, target_id)

    response = gemini_client.post(
        f"/api/v1/works/chapters/{target_id}/continue",
        json={"instruction": "인증 경계", "target_words": 50},
    )

    assert attempts == 0
    assert response.text.count("event: error") == 1
    assert '"code": "PROVIDER_ERROR"' in response.text
    assert "credential is not configured" in response.text
    assert FOREIGN_SECRET not in response.text
    assert _chapter(gemini_client, work_id, target_id) == before
    assert _run(gemini_client, _capture_count, target_id) == 0


def test_gemini_model_config_rejects_output_above_official_capability(
    gemini_client: TestClient,
) -> None:
    response = gemini_client.post(
        "/api/v1/model-configs",
        json={
            "provider": "gemini",
            "model_name": "gemini-3.8-flash",
            "max_tokens": 65_537,
            "context_window": 1_048_576,
            "is_default": True,
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "VALIDATION_ERROR",
        "message": "max_tokens exceeds model capability",
        "details": {"capability": 65_536},
    }


def test_existing_oversize_model_config_is_clamped_at_provider_resolution(
    gemini_client: TestClient,
) -> None:
    state = cast(Any, gemini_client.app).state

    resolved = _run(
        gemini_client,
        _seed_and_resolve_oversize_config,
        state.settings,
        state.registry,
    )

    assert resolved == (65_536, 1_048_576)
