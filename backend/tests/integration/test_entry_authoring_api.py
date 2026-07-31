"""Authenticated user-authoring and Entry read/audit API integration tests."""
from __future__ import annotations

import base64
import json
from datetime import datetime
from functools import partial
from typing import cast

from app.config import get_settings
from app.core.pagination import encode_cursor
from app.db.base import utcnow
from app.models.character import Character
from app.models.entry import Entry
from app.models.novel import Work
from app.models.user import User
from app.schemas.entry import (
    EntryCreate,
    EntryProvenance,
    EntryScope,
    EntryStatus,
    EntryType,
    ProvenanceCaptureMethod,
    ProvenanceSourceKind,
)
from app.services.entry_service import EntryService

DEFAULT_USER_ID = get_settings().DEFAULT_USER_ID
FOREIGN_USER_ID = "00000000-0000-0000-0000-000000000099"


def _run(client, function, *args, **kwargs):
    assert client.portal is not None
    call = partial(function, client.app.state.sessionmaker, *args, **kwargs)
    return client.portal.call(call)


def _human_provenance() -> EntryProvenance:
    return EntryProvenance(
        source_kind=ProvenanceSourceKind.USER,
        capture_method=ProvenanceCaptureMethod.HUMAN_AUTHORED,
        producer="entry-authoring-api-test",
    )


def _proposed_note(content: str) -> EntryCreate:
    return EntryCreate(
        scope_kind=EntryScope.USER,
        type=EntryType.NOTE,
        status=EntryStatus.PROPOSED,
        content=content,
        provenance=_human_provenance(),
    )


async def _ensure_user(session, user_id: str) -> None:
    if await session.get(User, user_id) is None:
        session.add(
            User(
                id=user_id,
                email=f"{user_id}@entry-authoring.test",
                display_name="Entry authoring owner",
            )
        )
        await session.commit()


async def _seed_history(sessionmaker) -> dict[str, str]:
    async with sessionmaker() as session:
        await _ensure_user(session, DEFAULT_USER_ID)
        await _ensure_user(session, FOREIGN_USER_ID)
        service = EntryService()

        captured = await service.create(
            session,
            DEFAULT_USER_ID,
            EntryCreate(
                scope_kind=EntryScope.USER,
                type=EntryType.NOTE,
                status=EntryStatus.CAPTURED,
                content="Captured authoring history",
                provenance=_human_provenance(),
            ),
        )
        proposed = await service.create(
            session, DEFAULT_USER_ID, _proposed_note("Proposed review history")
        )
        canon = await service.create(
            session, DEFAULT_USER_ID, _proposed_note("Current canon history")
        )
        canon = await service.update_status(
            session, DEFAULT_USER_ID, canon.id, EntryStatus.CANON
        )
        rejected = await service.create(
            session, DEFAULT_USER_ID, _proposed_note("Rejected review history")
        )
        rejected = await service.update_status(
            session, DEFAULT_USER_ID, rejected.id, EntryStatus.REJECTED
        )
        old_canon = await service.create(
            session, DEFAULT_USER_ID, _proposed_note("Superseded canon history")
        )
        old_canon = await service.update_status(
            session, DEFAULT_USER_ID, old_canon.id, EntryStatus.CANON
        )
        replacement = await service.create(
            session, DEFAULT_USER_ID, _proposed_note("Replacement canon history")
        )
        superseded, replacement = await service.supersede(
            session, DEFAULT_USER_ID, old_canon.id, replacement.id
        )
        foreign = await service.create(
            session, FOREIGN_USER_ID, _proposed_note("Foreign canonical history")
        )
        foreign = await service.update_status(
            session, FOREIGN_USER_ID, foreign.id, EntryStatus.CANON
        )
        return {
            "captured": captured.id,
            "proposed": proposed.id,
            "canon": canon.id,
            "rejected": rejected.id,
            "superseded": superseded.id,
            "replacement": replacement.id,
            "foreign": foreign.id,
        }


async def _seed_owned_and_foreign_anchors(sessionmaker) -> dict[str, str]:
    async with sessionmaker() as session:
        await _ensure_user(session, DEFAULT_USER_ID)
        await _ensure_user(session, FOREIGN_USER_ID)
        work = Work(user_id=DEFAULT_USER_ID, title="Owned Entry work")
        character = Character(user_id=DEFAULT_USER_ID, name="Owned Entry character")
        foreign_work = Work(user_id=FOREIGN_USER_ID, title="Foreign Entry work")
        deleted_work = Work(user_id=DEFAULT_USER_ID, title="Deleted Entry work")
        session.add_all([work, character, foreign_work, deleted_work])
        await session.flush()
        deleted_work.deleted_at = utcnow()
        await session.commit()
        return {
            "work_id": work.id,
            "character_id": character.id,
            "foreign_work_id": foreign_work.id,
            "deleted_work_id": deleted_work.id,
        }


def _authoring_payload(**overrides) -> dict:
    return {
        "scope_kind": "user",
        "type": "note",
        "title": "Author-created canon",
        "content": "The author deliberately confirms this fact.",
        "data": {"source": "manual"},
        "priority": 70,
        **overrides,
    }


def test_user_authoring_creates_owned_canon_with_server_provenance(client) -> None:
    response = client.post("/api/v1/entries", json=_authoring_payload())

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == EntryStatus.CANON.value
    assert body["user_id"] == DEFAULT_USER_ID
    assert body["accepted_at"] is not None
    assert body["content"] == "The author deliberately confirms this fact."
    assert body["provenance"] == {
        "source_kind": ProvenanceSourceKind.USER.value,
        "source_id": DEFAULT_USER_ID,
        "locator": {},
        "capture_method": ProvenanceCaptureMethod.HUMAN_AUTHORED.value,
        "producer": "user-authoring-api",
    }


def test_authoring_rejects_client_lifecycle_owner_and_ai_producer_controls(client) -> None:
    prohibited = {
        "status": "canon",
        "user_id": FOREIGN_USER_ID,
        "provenance": {"capture_method": "ai-extracted"},
        "producer": "analyst",
        "confidence": 1.0,
    }
    for field, value in prohibited.items():
        response = client.post("/api/v1/entries", json=_authoring_payload(**{field: value}))
        assert response.status_code == 422, response.text
        assert field in {error["loc"][-1] for error in response.json()["error"]["details"]["errors"]}


def test_authoring_reuses_owner_and_active_anchor_validation(client) -> None:
    anchors = _run(client, _seed_owned_and_foreign_anchors)
    base = _authoring_payload(
        scope_kind="work",
        type="story.knowledge",
        subject_type="character",
        subject_id=anchors["character_id"],
    )

    owned = client.post("/api/v1/entries", json={**base, "scope_id": anchors["work_id"]})
    assert owned.status_code == 201, owned.text

    foreign = client.post(
        "/api/v1/entries", json={**base, "scope_id": anchors["foreign_work_id"]}
    )
    assert foreign.status_code == 400, foreign.text
    assert "scope_id" in foreign.json()["error"]["message"]

    deleted = client.post(
        "/api/v1/entries", json={**base, "scope_id": anchors["deleted_work_id"]}
    )
    assert deleted.status_code == 400, deleted.text
    assert "scope_id" in deleted.json()["error"]["message"]

    missing = client.post(
        "/api/v1/entries", json={**base, "scope_id": "missing-work"}
    )
    assert missing.status_code == 400, missing.text

    invalid_type = client.post("/api/v1/entries", json=_authoring_payload(type="misc"))
    assert invalid_type.status_code == 422, invalid_type.text


def test_canon_list_is_default_owner_scoped_and_audit_is_explicit(client) -> None:
    history = _run(client, _seed_history)

    default_list = client.get("/api/v1/entries")
    assert default_list.status_code == 200, default_list.text
    default_items = default_list.json()["items"]
    default_ids = {item["id"] for item in default_items}
    assert history["canon"] in default_ids
    assert history["replacement"] in default_ids
    assert history["captured"] not in default_ids
    assert history["proposed"] not in default_ids
    assert history["rejected"] not in default_ids
    assert history["superseded"] not in default_ids
    assert history["foreign"] not in default_ids
    assert {item["status"] for item in default_items} == {EntryStatus.CANON.value}

    requires_opt_in = client.get("/api/v1/entries?status=proposed")
    assert requires_opt_in.status_code == 400, requires_opt_in.text

    for entry_status in EntryStatus:
        response = client.get(
            f"/api/v1/entries?include_history=true&status={entry_status.value}"
        )
        assert response.status_code == 200, response.text
        items = response.json()["items"]
        assert all(item["status"] == entry_status.value for item in items)
        assert history[entry_status.value] in {item["id"] for item in items}

    all_history = client.get("/api/v1/entries?include_history=true")
    assert all_history.status_code == 200, all_history.text
    assert {item["id"] for item in all_history.json()["items"]}.issuperset(
        set(history.values()) - {history["foreign"]}
    )


def test_entry_detail_exposes_status_without_cross_owner_leak(client) -> None:
    history = _run(client, _seed_history)

    captured = client.get(f"/api/v1/entries/{history['captured']}")
    assert captured.status_code == 200, captured.text
    assert captured.json()["status"] == EntryStatus.CAPTURED.value

    foreign = client.get(f"/api/v1/entries/{history['foreign']}")
    assert foreign.status_code == 404, foreign.text
    assert foreign.json()["error"]["message"] == "Entry not found"

    missing = client.get("/api/v1/entries/missing-entry")
    assert missing.status_code == 404, missing.text


def test_entry_list_filters_and_cursor_ordering(client) -> None:
    anchors = _run(client, _seed_owned_and_foreign_anchors)
    scoped = client.post(
        "/api/v1/entries",
        json=_authoring_payload(
            scope_kind="work",
            scope_id=anchors["work_id"],
            type="story.knowledge",
            subject_type="character",
            subject_id=anchors["character_id"],
            content="Only the heroine knows the secret passage.",
        ),
    )
    assert scoped.status_code == 201, scoped.text
    scoped_id = scoped.json()["id"]

    filtered = client.get(
        "/api/v1/entries",
        params={
            "scope": "work",
            "scope_id": anchors["work_id"],
            "type": "story.knowledge",
            "subject_type": "character",
            "subject_id": anchors["character_id"],
        },
    )
    assert filtered.status_code == 200, filtered.text
    assert [item["id"] for item in filtered.json()["items"]] == [scoped_id]

    first = client.post(
        "/api/v1/entries",
        json=_authoring_payload(type="user.preference", content="Prefer close third person."),
    )
    second = client.post(
        "/api/v1/entries",
        json=_authoring_payload(type="user.preference", content="Keep dialogue concise."),
    )
    assert first.status_code == second.status_code == 201
    first_page = client.get("/api/v1/entries?type=user.preference&limit=1")
    assert first_page.status_code == 200, first_page.text
    cursor = first_page.json()["next_cursor"]
    assert cursor is not None
    second_page = client.get(
        "/api/v1/entries", params={"type": "user.preference", "limit": 1, "cursor": cursor}
    )
    assert second_page.status_code == 200, second_page.text
    page_ids = {item["id"] for item in first_page.json()["items"]} | {
        item["id"] for item in second_page.json()["items"]
    }
    assert {first.json()["id"], second.json()["id"]}.issubset(page_ids)
    assert not (
        {item["id"] for item in first_page.json()["items"]}
        & {item["id"] for item in second_page.json()["items"]}
    )


def test_canon_correction_uses_supersession_without_a_generic_patch(client) -> None:
    initial = client.post(
        "/api/v1/entries",
        json=_authoring_payload(content="The gate is locked."),
    )
    assert initial.status_code == 201, initial.text
    initial_id = initial.json()["id"]

    correction = client.post(
        "/api/v1/entries",
        json=_authoring_payload(
            content="The gate is open.",
            supersedes_entry_id=initial_id,
        ),
    )
    assert correction.status_code == 201, correction.text
    assert correction.json()["status"] == EntryStatus.CANON.value

    old = client.get(f"/api/v1/entries/{initial_id}")
    assert old.status_code == 200, old.text
    assert old.json()["status"] == EntryStatus.SUPERSEDED.value
    assert old.json()["superseded_by_entry_id"] == correction.json()["id"]
    assert old.json()["content"] == "The gate is locked."

    assert client.patch(f"/api/v1/entries/{initial_id}", json={"content": "overwrite"}).status_code == 405


async def _soft_delete_work(sessionmaker, work_id: str) -> None:
    async with sessionmaker() as session:
        work = await session.get(Work, work_id)
        assert work is not None
        work.deleted_at = utcnow()
        await session.commit()


def test_list_rejects_incomplete_scope_and_invalid_cursor_filters(client) -> None:
    assert client.get("/api/v1/entries?scope=work").status_code == 400
    assert client.get("/api/v1/entries?scope=user&scope_id=unexpected").status_code == 400
    assert client.get("/api/v1/entries?cursor=not-a-cursor").status_code == 400


def test_default_canon_list_excludes_orphaned_entries_but_audit_retains_them(client) -> None:
    anchors = _run(client, _seed_owned_and_foreign_anchors)
    created = client.post(
        "/api/v1/entries",
        json=_authoring_payload(
            scope_kind="work",
            scope_id=anchors["work_id"],
            type="story.fact",
            content="This fact becomes historical when the work is deleted.",
        ),
    )
    assert created.status_code == 201, created.text
    entry_id = created.json()["id"]
    _run(client, _soft_delete_work, anchors["work_id"])

    default_list = client.get("/api/v1/entries")
    assert default_list.status_code == 200, default_list.text
    assert entry_id not in {item["id"] for item in default_list.json()["items"]}

    audit = client.get("/api/v1/entries?include_history=true&status=canon")
    assert audit.status_code == 200, audit.text
    assert entry_id in {item["id"] for item in audit.json()["items"]}


def test_list_rejects_decodable_cursor_with_non_string_identifier(client) -> None:
    cursor = encode_cursor("2026-07-28T00:00:00", cast(str, ["not-an-entry-id"]))
    response = client.get("/api/v1/entries", params={"cursor": cursor})
    assert response.status_code == 400, response.text
    assert response.json()["error"]["message"] == "Invalid Entry cursor"


def test_default_page_scans_past_orphans_before_selecting_live_entries(client) -> None:
    orphan_anchors = _run(client, _seed_owned_and_foreign_anchors)
    orphaned = client.post(
        "/api/v1/entries",
        json=_authoring_payload(
            scope_kind="work",
            scope_id=orphan_anchors["work_id"],
            type="story.promise",
            content="This orphaned promise sorts before the live promise.",
        ),
    )
    assert orphaned.status_code == 201, orphaned.text
    _run(client, _soft_delete_work, orphan_anchors["work_id"])

    live_anchors = _run(client, _seed_owned_and_foreign_anchors)
    live = client.post(
        "/api/v1/entries",
        json=_authoring_payload(
            scope_kind="work",
            scope_id=live_anchors["work_id"],
            type="story.promise",
            content="This live promise must fill the first visible page.",
        ),
    )
    assert live.status_code == 201, live.text

    page = client.get("/api/v1/entries", params={"type": "story.promise", "limit": 1})
    assert page.status_code == 200, page.text
    assert [item["id"] for item in page.json()["items"]] == [live.json()["id"]]
    assert page.json()["next_cursor"] is None


async def _force_created_at(sessionmaker, entry_ids: list[str], moment: datetime) -> None:
    """Collapse distinct creation instants so the id tie-break becomes observable."""
    async with sessionmaker() as session:
        for entry_id in entry_ids:
            entry = await session.get(Entry, entry_id)
            assert entry is not None
            entry.created_at = moment
        await session.commit()


def test_cursor_pagination_breaks_ties_on_identical_created_at(client) -> None:
    anchors = _run(client, _seed_owned_and_foreign_anchors)
    created_ids = []
    for index in range(3):
        response = client.post(
            "/api/v1/entries",
            json=_authoring_payload(
                scope_kind="work",
                scope_id=anchors["work_id"],
                type="story.fact",
                content=f"Tie-break fact {index}.",
            ),
        )
        assert response.status_code == 201, response.text
        created_ids.append(response.json()["id"])

    shared_moment = datetime.fromisoformat("2026-01-02T03:04:05.678901+00:00")
    _run(client, _force_created_at, created_ids, shared_moment)

    scope_filter = {
        "scope": "work",
        "scope_id": anchors["work_id"],
        "type": "story.fact",
        "limit": 1,
    }
    visited: list[str] = []
    cursor: str | None = None
    for _ in range(len(created_ids)):
        params = dict(scope_filter)
        if cursor is not None:
            params["cursor"] = cursor
        page = client.get("/api/v1/entries", params=params)
        assert page.status_code == 200, page.text
        body = page.json()
        assert len(body["items"]) == 1
        visited.append(body["items"][0]["id"])
        cursor = body["next_cursor"]

    # Identical timestamps must still advance deterministically by id, so no
    # Entry is repeated and none is skipped.
    assert visited == sorted(created_ids)
    assert cursor is None


def test_list_rejects_every_malformed_cursor_shape(client) -> None:
    def _encoded(payload: object) -> str:
        return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")

    malformed = [
        "!!!not-base64!!!",
        base64.urlsafe_b64encode(b"plain text, not json").decode("utf-8"),
        _encoded({"i": "entry-id"}),
        _encoded({"c": "2026-07-28T00:00:00"}),
        _encoded({"c": 20260728, "i": "entry-id"}),
        _encoded({"c": "2026-07-28T00:00:00", "i": 42}),
        encode_cursor("not-a-timestamp", "entry-id"),
    ]
    for cursor in malformed:
        response = client.get("/api/v1/entries", params={"cursor": cursor})
        # A rejected cursor must fail loudly instead of silently restarting at
        # the first page, which would repeat records to the caller.
        assert response.status_code == 400, (cursor, response.text)
        assert response.json()["error"]["message"] == "Invalid Entry cursor"


def _scope_audit_state(client, work_id: str) -> list[dict[str, str | None]]:
    """Snapshot every persisted lifecycle fact for one work scope."""
    audit = client.get(
        "/api/v1/entries",
        params={
            "include_history": "true",
            "scope": "work",
            "scope_id": work_id,
            "type": "story.fact",
            "limit": 100,
        },
    )
    assert audit.status_code == 200, audit.text
    return sorted(
        (
            {
                "id": item["id"],
                "content": item["content"],
                "status": item["status"],
                "superseded_by_entry_id": item["superseded_by_entry_id"],
                "accepted_at": item["accepted_at"],
                "superseded_at": item["superseded_at"],
            }
            for item in audit.json()["items"]
        ),
        key=lambda item: cast(str, item["id"]),
    )


def test_failed_correction_does_not_persist_the_replacement(client) -> None:
    anchors = _run(client, _seed_owned_and_foreign_anchors)
    scoped = partial(
        _authoring_payload,
        scope_kind="work",
        scope_id=anchors["work_id"],
        type="story.fact",
    )

    original = client.post("/api/v1/entries", json=scoped(content="Rollback origin fact."))
    assert original.status_code == 201, original.text
    original_id = original.json()["id"]

    accepted_correction = client.post(
        "/api/v1/entries",
        json=scoped(content="Rollback first correction.", supersedes_entry_id=original_id),
    )
    assert accepted_correction.status_code == 201, accepted_correction.text

    before = _scope_audit_state(client, anchors["work_id"])

    # The original is superseded now, so a second correction against it must be
    # refused by the same atomic lifecycle implementation.
    rejected_correction = client.post(
        "/api/v1/entries",
        json=scoped(
            content="Rollback orphaned replacement.",
            supersedes_entry_id=original_id,
        ),
    )
    assert rejected_correction.status_code == 400, rejected_correction.text
    assert "canon" in rejected_correction.json()["error"]["message"]

    after = _scope_audit_state(client, anchors["work_id"])
    # A failed correction must leave no partially written replacement behind and
    # must not mutate the existing lifecycle records.
    assert after == before
    contents = [cast(str, item["content"]) for item in after]
    assert "Rollback orphaned replacement." not in contents
    assert sorted(contents) == ["Rollback first correction.", "Rollback origin fact."]

    detail = client.get(f"/api/v1/entries/{original_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["status"] == EntryStatus.SUPERSEDED.value
    assert detail.json()["superseded_by_entry_id"] == accepted_correction.json()["id"]


def test_same_cursor_replay_returns_the_identical_page(client) -> None:
    anchors = _run(client, _seed_owned_and_foreign_anchors)
    for index in range(3):
        response = client.post(
            "/api/v1/entries",
            json=_authoring_payload(
                scope_kind="work",
                scope_id=anchors["work_id"],
                type="story.fact",
                content=f"Cursor replay fact {index}.",
            ),
        )
        assert response.status_code == 201, response.text

    params = {
        "scope": "work",
        "scope_id": anchors["work_id"],
        "type": "story.fact",
        "limit": 2,
    }
    first_page = client.get("/api/v1/entries", params=params)
    assert first_page.status_code == 200, first_page.text
    cursor = first_page.json()["next_cursor"]
    assert cursor is not None
    first_ids = [item["id"] for item in first_page.json()["items"]]
    assert len(first_ids) == 2

    replayed = [
        client.get("/api/v1/entries", params={**params, "cursor": cursor}) for _ in range(2)
    ]
    for response in replayed:
        assert response.status_code == 200, response.text
    bodies = [response.json() for response in replayed]
    # Re-requesting with an unchanged cursor is a read, so it must be repeatable
    # and must never hand back records the caller already consumed.
    assert bodies[0] == bodies[1]
    assert [item["id"] for item in bodies[0]["items"]] not in ([], first_ids)
    assert not set(first_ids) & {item["id"] for item in bodies[0]["items"]}
    assert bodies[0]["next_cursor"] is None


def test_cursor_beyond_all_records_returns_empty_page_not_the_first_page(client) -> None:
    anchors = _run(client, _seed_owned_and_foreign_anchors)
    created = client.post(
        "/api/v1/entries",
        json=_authoring_payload(
            scope_kind="work",
            scope_id=anchors["work_id"],
            type="story.fact",
            content="Far future cursor must not wrap around to this record.",
        ),
    )
    assert created.status_code == 201, created.text

    params = {
        "scope": "work",
        "scope_id": anchors["work_id"],
        "type": "story.fact",
        "limit": 10,
    }
    baseline = client.get("/api/v1/entries", params=params)
    assert baseline.status_code == 200, baseline.text
    assert [item["id"] for item in baseline.json()["items"]] == [created.json()["id"]]

    exhausted = client.get(
        "/api/v1/entries",
        params={**params, "cursor": encode_cursor("2999-01-01T00:00:00", "zzzzzzzz")},
    )
    assert exhausted.status_code == 200, exhausted.text
    # An exhausted cursor stops cleanly; it must not silently restart the page
    # sequence, which would re-deliver already consumed records.
    assert exhausted.json()["items"] == []
    assert exhausted.json()["next_cursor"] is None
