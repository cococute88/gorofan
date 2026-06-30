"""Integration tests: health + CRUD + ownership (design 8.15, Property 1/2)."""
from __future__ import annotations


def test_health(client):
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/readyz").status_code == 200


def test_world_and_character_crud(client):
    # create world
    w = client.post("/api/v1/worlds", json={"name": "아르카디아", "description": "중세 판타지"})
    assert w.status_code == 201, w.text
    world_id = w.json()["id"]

    # create character linked to the world (INV-2 satisfied)
    c = client.post(
        "/api/v1/characters",
        json={"name": "루나", "world_id": world_id, "greeting": "안녕!"},
    )
    assert c.status_code == 201, c.text
    char_id = c.json()["id"]

    # list characters
    lst = client.get("/api/v1/characters")
    assert lst.status_code == 200
    assert any(item["id"] == char_id for item in lst.json()["items"])

    # update + soft delete
    upd = client.patch(f"/api/v1/characters/{char_id}", json={"speech_style": "다정한 반말"})
    assert upd.status_code == 200
    assert upd.json()["speech_style"] == "다정한 반말"

    dele = client.delete(f"/api/v1/characters/{char_id}")
    assert dele.status_code == 204


def test_character_rejects_foreign_world(client):
    # world_id that does not exist / not owned -> validation error (Property 2)
    r = client.post(
        "/api/v1/characters",
        json={"name": "고스트", "world_id": "00000000-0000-0000-0000-0000deadbeef"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_chapter_index_unique_and_reorder(client):
    work = client.post("/api/v1/works", json={"title": "별빛 연대기", "genre": "판타지"})
    assert work.status_code == 201, work.text
    work_id = work.json()["id"]

    c1 = client.post(f"/api/v1/works/{work_id}/chapters", json={"title": "1화"})
    c2 = client.post(f"/api/v1/works/{work_id}/chapters", json={"title": "2화"})
    assert c1.json()["index"] == 1
    assert c2.json()["index"] == 2  # Property 3: unique, monotonic assignment

    # reorder
    r = client.patch(
        f"/api/v1/works/{work_id}/chapters:reorder",
        json={"ordered_chapter_ids": [c2.json()["id"], c1.json()["id"]]},
    )
    assert r.status_code == 204
    chapters = client.get(f"/api/v1/works/{work_id}/chapters").json()
    by_id = {c["id"]: c["index"] for c in chapters}
    assert by_id[c2.json()["id"]] == 1


def test_credential_is_masked(client):
    r = client.post(
        "/api/v1/credentials",
        json={"provider": "openai", "api_key": "sk-proj-secretvalue-1234", "label": "main"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "secretvalue" not in str(body)  # Property 8
    assert body["masked_key"].endswith("1234")


def test_providers_list(client):
    r = client.get("/api/v1/providers")
    assert r.status_code == 200
    names = {p["provider"] for p in r.json()}
    assert {"openai", "anthropic", "gemini", "ollama"}.issubset(names)
