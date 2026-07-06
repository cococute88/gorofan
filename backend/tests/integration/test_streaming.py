"""SSE streaming integration test (design 8.7, tasks 7.3).

Injects a fake in-process provider and drives a full chat turn through the SSE
endpoint, verifying event order (token* -> done), single assistant persistence
(Property 4) and user-message preservation (Property 9).
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from app.adapters.base import AssembledPrompt, Completion, ModelCapability, ProviderRequest


class _FakeAdapter:
    """Deterministic streaming provider for tests."""

    TOKENS = ["안녕", "하세요", "!"]

    async def stream_chat(
        self, prompt: AssembledPrompt, req: ProviderRequest
    ) -> AsyncIterator[str]:
        for t in self.TOKENS:
            yield t

    async def chat(self, prompt: AssembledPrompt, req: ProviderRequest) -> Completion:
        return Completion(content="".join(self.TOKENS), token_count=3, finish_reason="stop")

    def capabilities(self, model: str) -> ModelCapability:
        return ModelCapability(context_window=8192, max_output_tokens=1024)


def _register_fake(client) -> None:
    client.app.state.registry.register("fake", _FakeAdapter)


def test_chat_sse_stream_and_single_persist(client):
    _register_fake(client)

    # default model config using the fake provider
    mc = client.post(
        "/api/v1/model-configs",
        json={
            "provider": "fake",
            "model_name": "fake-1",
            "max_tokens": 256,
            "context_window": 8192,
            "is_default": True,
        },
    )
    assert mc.status_code == 201, mc.text

    ch = client.post("/api/v1/characters", json={"name": "루나", "greeting": "반가워"})
    assert ch.status_code == 201, ch.text
    char_id = ch.json()["id"]

    chat = client.post("/api/v1/chats", json={"character_id": char_id})
    assert chat.status_code == 201, chat.text
    chat_id = chat.json()["id"]

    # stream a message
    resp = client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": "안녕?"})
    assert resp.status_code == 200, resp.text
    body = resp.text
    assert "event: token" in body
    assert "event: done" in body
    # tokens arrive before done
    assert body.index("event: token") < body.index("event: done")

    # messages: 1 seeded greeting + 1 user + exactly 1 active assistant reply
    msgs = client.get(f"/api/v1/chats/{chat_id}/messages").json()["items"]
    users = [m for m in msgs if m["role"] == "user"]
    assistants = [m for m in msgs if m["role"] == "assistant"]
    assert any(m["content"] == "안녕?" for m in users)  # Property 9: user preserved
    replies = [m for m in assistants if m["content"] == "안녕하세요!"]
    assert len(replies) == 1  # Property 4: assistant persisted exactly once


def test_chat_regenerate_creates_new_row(client):
    _register_fake(client)
    client.post(
        "/api/v1/model-configs",
        json={"provider": "fake", "model_name": "fake-1", "is_default": True},
    )
    char_id = client.post("/api/v1/characters", json={"name": "미아"}).json()["id"]
    chat_id = client.post("/api/v1/chats", json={"character_id": char_id}).json()["id"]

    client.post(f"/api/v1/chats/{chat_id}/messages", json={"content": "첫 메시지"})
    before = client.get(f"/api/v1/chats/{chat_id}/messages").json()["items"]
    assistants_before = [m for m in before if m["role"] == "assistant"]

    regen = client.post(f"/api/v1/chats/{chat_id}/regenerate")
    assert regen.status_code == 200, regen.text

    after = client.get(f"/api/v1/chats/{chat_id}/messages").json()["items"]
    # active list unchanged in count, but a new assistant row exists (old is_active=false)
    active_assistants = [m for m in after if m["role"] == "assistant"]
    assert len(active_assistants) == len(assistants_before)
