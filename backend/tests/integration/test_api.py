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


def test_persona_crud(client):
    # create
    r = client.post("/api/v1/personas", json={"name": "여행자", "description": "호기심 많은"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    # list
    lst = client.get("/api/v1/personas")
    assert lst.status_code == 200
    assert any(p["id"] == pid for p in lst.json()["items"])

    # get
    assert client.get(f"/api/v1/personas/{pid}").json()["name"] == "여행자"

    # update
    upd = client.patch(f"/api/v1/personas/{pid}", json={"description": "차분한"})
    assert upd.status_code == 200
    assert upd.json()["description"] == "차분한"
    assert upd.json()["name"] == "여행자"  # unset field preserved

    # delete
    assert client.delete(f"/api/v1/personas/{pid}").status_code == 204
    assert client.get(f"/api/v1/personas/{pid}").status_code == 404


def test_work_character_link_list_unlink(client):
    work_id = client.post("/api/v1/works", json={"title": "링크 테스트"}).json()["id"]
    char_id = client.post("/api/v1/characters", json={"name": "주인공"}).json()["id"]

    # empty initially
    assert client.get(f"/api/v1/works/{work_id}/characters").json() == []

    # link
    link = client.post(
        f"/api/v1/works/{work_id}/characters",
        json={"character_id": char_id, "role_in_work": "주연"},
    )
    assert link.status_code == 201, link.text

    # duplicate link rejected (Conflict)
    dup = client.post(
        f"/api/v1/works/{work_id}/characters", json={"character_id": char_id}
    )
    assert dup.status_code == 409

    # list reflects the link
    listed = client.get(f"/api/v1/works/{work_id}/characters").json()
    assert [wc["character_id"] for wc in listed] == [char_id]
    assert listed[0]["role_in_work"] == "주연"

    # unlink
    assert client.delete(f"/api/v1/works/{work_id}/characters/{char_id}").status_code == 204
    assert client.get(f"/api/v1/works/{work_id}/characters").json() == []
    # unlinking again is a 404
    assert client.delete(f"/api/v1/works/{work_id}/characters/{char_id}").status_code == 404
