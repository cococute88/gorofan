"""Authenticated Entry Review Card API integration tests."""
from __future__ import annotations

from functools import partial

from starlette.testclient import TestClient

from app.config import get_settings
from app.db.base import utcnow
from app.models.character import Character
from app.models.novel import Chapter, Work
from app.models.user import User
from app.schemas.entry import (
    EntryCreate,
    EntryProvenance,
    EntryScope,
    EntryStatus,
    EntrySubjectType,
    EntryType,
    ProvenanceCaptureMethod,
    ProvenanceSourceKind,
)
from app.services.entry_service import EntryService

DEFAULT_USER_ID = get_settings().DEFAULT_USER_ID


def _provenance(
    *,
    source_kind: ProvenanceSourceKind = ProvenanceSourceKind.USER,
    source_id: str | None = None,
) -> EntryProvenance:
    return EntryProvenance(
        source_kind=source_kind,
        source_id=source_id,
        capture_method=ProvenanceCaptureMethod.AI_EXTRACTED,
        producer="review-api-test",
    )


def _run(client, function, *args, **kwargs):
    assert client.portal is not None
    call = partial(function, client.app.state.sessionmaker, *args, **kwargs)
    return client.portal.call(call)


async def _seed_note(
    sessionmaker,
    content: str,
    *,
    user_id: str = DEFAULT_USER_ID,
    status: EntryStatus = EntryStatus.PROPOSED,
) -> str:
    async with sessionmaker() as session:
        if await session.get(User, user_id) is None:
            session.add(
                User(
                    id=user_id,
                    email=f"{user_id}@review.test",
                    display_name="Review owner",
                )
            )
            await session.commit()
        provenance = _provenance()
        if status is EntryStatus.CAPTURED:
            provenance = provenance.model_copy(
                update={"capture_method": ProvenanceCaptureMethod.HUMAN_AUTHORED}
            )
        entry = await EntryService().create(
            session,
            user_id,
            EntryCreate(
                scope_kind=EntryScope.USER,
                type=EntryType.NOTE,
                status=status,
                title="Original title",
                content=content,
                data={"version": 1},
                provenance=provenance,
                confidence=0.8,
                priority=60,
            ),
        )
        return entry.id


async def _seed_terminal_notes(sessionmaker) -> dict[str, str]:
    async with sessionmaker() as session:
        service = EntryService()
        canon = await service.create(
            session,
            DEFAULT_USER_ID,
            EntryCreate(
                scope_kind=EntryScope.USER,
                type=EntryType.NOTE,
                status=EntryStatus.PROPOSED,
                content="terminal canon",
                provenance=_provenance(),
                confidence=0.8,
            ),
        )
        canon = await service.update_status(
            session, DEFAULT_USER_ID, canon.id, EntryStatus.CANON
        )
        rejected = await service.create(
            session,
            DEFAULT_USER_ID,
            EntryCreate(
                scope_kind=EntryScope.USER,
                type=EntryType.NOTE,
                status=EntryStatus.PROPOSED,
                content="terminal rejected",
                provenance=_provenance(),
                confidence=0.8,
            ),
        )
        rejected = await service.update_status(
            session, DEFAULT_USER_ID, rejected.id, EntryStatus.REJECTED
        )
        replacement = await service.create(
            session,
            DEFAULT_USER_ID,
            EntryCreate(
                scope_kind=EntryScope.USER,
                type=EntryType.NOTE,
                status=EntryStatus.PROPOSED,
                content="terminal replacement",
                provenance=_provenance(),
                confidence=0.8,
            ),
        )
        superseded, _ = await service.supersede(
            session, DEFAULT_USER_ID, canon.id, replacement.id
        )
        return {
            "canon": replacement.id,
            "rejected": rejected.id,
            "superseded": superseded.id,
        }


async def _seed_duplicate_single_current(
    sessionmaker, entry_type: EntryType
) -> str:
    async with sessionmaker() as session:
        service = EntryService()
        work = Work(user_id=DEFAULT_USER_ID, title=f"{entry_type.value} work")
        session.add(work)
        await session.flush()
        if entry_type is EntryType.RELATIONSHIP_STATE:
            first = Character(user_id=DEFAULT_USER_ID, name="First reviewer")
            second = Character(user_id=DEFAULT_USER_ID, name="Second reviewer")
            session.add_all([first, second])
            await session.commit()
            common = {
                "scope_kind": EntryScope.WORK,
                "scope_id": work.id,
                "subject_type": EntrySubjectType.CHARACTER_PAIR,
                "subject_data": {"character_ids": [first.id, second.id]},
                "type": entry_type,
            }
        else:
            chapter = Chapter(
                work_id=work.id,
                user_id=DEFAULT_USER_ID,
                index=1,
                title="Review chapter",
            )
            session.add(chapter)
            await session.commit()
            common = {
                "scope_kind": EntryScope.WORK,
                "scope_id": work.id,
                "subject_type": EntrySubjectType.CHAPTER,
                "subject_id": chapter.id,
                "type": entry_type,
            }

        current = await service.create(
            session,
            DEFAULT_USER_ID,
            EntryCreate(
                **common,
                status=EntryStatus.PROPOSED,
                content="Current canon",
                provenance=_provenance(),
                confidence=0.9,
            ),
        )
        await service.update_status(
            session, DEFAULT_USER_ID, current.id, EntryStatus.CANON
        )
        replacement = await service.create(
            session,
            DEFAULT_USER_ID,
            EntryCreate(
                **common,
                status=EntryStatus.PROPOSED,
                content="Conflicting replacement",
                provenance=_provenance(),
                confidence=0.9,
            ),
        )
        return replacement.id


async def _seed_soft_deleted_scope(sessionmaker) -> str:
    async with sessionmaker() as session:
        work = Work(user_id=DEFAULT_USER_ID, title="Deleted review scope")
        session.add(work)
        await session.commit()
        entry = await EntryService().create(
            session,
            DEFAULT_USER_ID,
            EntryCreate(
                scope_kind=EntryScope.WORK,
                scope_id=work.id,
                type=EntryType.STORY_FACT,
                status=EntryStatus.PROPOSED,
                content="Orphaned proposal",
                provenance=_provenance(),
                confidence=0.8,
            ),
        )
        work.deleted_at = utcnow()
        await session.commit()
        return entry.id


async def _seed_soft_deleted_provenance(sessionmaker) -> str:
    async with sessionmaker() as session:
        work = Work(user_id=DEFAULT_USER_ID, title="Deleted provenance work")
        session.add(work)
        await session.flush()
        chapter = Chapter(
            work_id=work.id,
            user_id=DEFAULT_USER_ID,
            index=1,
            title="Deleted provenance chapter",
        )
        session.add(chapter)
        await session.commit()
        entry = await EntryService().create(
            session,
            DEFAULT_USER_ID,
            EntryCreate(
                scope_kind=EntryScope.USER,
                type=EntryType.NOTE,
                status=EntryStatus.PROPOSED,
                content="Proposal with stale provenance",
                provenance=_provenance(
                    source_kind=ProvenanceSourceKind.CHAPTER,
                    source_id=chapter.id,
                ),
                confidence=0.8,
            ),
        )
        work.deleted_at = utcnow()
        await session.commit()
        return entry.id


def test_review_list_detail_and_owner_boundary(client) -> None:
    owned_id = _run(client, _seed_note, "owned proposed review")
    captured_id = _run(
        client, _seed_note, "owned captured review", status=EntryStatus.CAPTURED
    )
    foreign_id = _run(
        client,
        _seed_note,
        "foreign proposed review",
        user_id="00000000-0000-0000-0000-000000000099",
    )

    response = client.get("/api/v1/entries/review")
    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()}
    assert owned_id in ids
    assert captured_id not in ids
    assert foreign_id not in ids

    detail = client.get(f"/api/v1/entries/review/{owned_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["content"] == "owned proposed review"
    assert client.get(f"/api/v1/entries/review/{foreign_id}").status_code == 404
    assert client.post(f"/api/v1/entries/review/{foreign_id}/accept").status_code == 404
    assert client.post(f"/api/v1/entries/review/{foreign_id}/reject").status_code == 404
    assert (
        client.post(
            f"/api/v1/entries/review/{foreign_id}/edit",
            json={"content": "cross-owner edit"},
        ).status_code
        == 404
    )


def test_review_accept_and_reject_are_explicit_transitions(client) -> None:
    accepted_id = _run(client, _seed_note, "accept this proposal")
    rejected_id = _run(client, _seed_note, "reject this proposal")

    accepted = client.post(f"/api/v1/entries/review/{accepted_id}/accept")
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == EntryStatus.CANON.value
    assert accepted.json()["accepted_at"] is not None

    rejected = client.post(f"/api/v1/entries/review/{rejected_id}/reject")
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == EntryStatus.REJECTED.value
    assert rejected.json()["rejected_at"] is not None


def test_review_edit_updates_only_proposed_editable_fields(client) -> None:
    entry_id = _run(client, _seed_note, "before edit")
    response = client.post(
        f"/api/v1/entries/review/{entry_id}/edit",
        json={
            "title": "Reviewed title",
            "content": "  after edit  ",
            "data": {"version": 2},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "Reviewed title"
    assert body["content"] == "after edit"
    assert body["data"] == {"version": 2}
    assert body["status"] == EntryStatus.PROPOSED.value
    assert body["provenance"]["capture_method"] == "human-edited"


def test_review_edit_rejects_terminal_entries(client) -> None:
    entries = _run(client, _seed_terminal_notes)
    for entry_id in entries.values():
        response = client.post(
            f"/api/v1/entries/review/{entry_id}/edit",
            json={"content": "must not change"},
        )
        assert response.status_code == 400, response.text
        assert response.json()["error"]["message"] == "Entry is not proposed for review"


def test_review_accept_reject_are_not_idempotent_successes(client) -> None:
    accepted_id = _run(client, _seed_note, "accept once")
    assert client.post(f"/api/v1/entries/review/{accepted_id}/accept").status_code == 200
    repeated = client.post(f"/api/v1/entries/review/{accepted_id}/accept")
    assert repeated.status_code == 400
    assert repeated.json()["error"]["details"]["status"] == EntryStatus.CANON.value

    captured_id = _run(
        client, _seed_note, "captured cannot reject via review", status=EntryStatus.CAPTURED
    )
    reject = client.post(f"/api/v1/entries/review/{captured_id}/reject")
    assert reject.status_code == 400
    assert reject.json()["error"]["details"]["status"] == EntryStatus.CAPTURED.value


def test_review_accept_preserves_single_current_relationship_policy(client) -> None:
    entry_id = _run(
        client, _seed_duplicate_single_current, EntryType.RELATIONSHIP_STATE
    )
    response = client.post(f"/api/v1/entries/review/{entry_id}/accept")
    assert response.status_code == 400, response.text
    assert "use supersede()" in response.json()["error"]["message"]


def test_review_accept_preserves_single_current_story_summary_policy(client) -> None:
    entry_id = _run(client, _seed_duplicate_single_current, EntryType.STORY_SUMMARY)
    response = client.post(f"/api/v1/entries/review/{entry_id}/accept")
    assert response.status_code == 400, response.text
    assert "use supersede()" in response.json()["error"]["message"]


def test_review_accept_rejects_soft_deleted_scope_and_provenance(client) -> None:
    scope_entry_id = _run(client, _seed_soft_deleted_scope)
    scope_response = client.post(
        f"/api/v1/entries/review/{scope_entry_id}/accept"
    )
    assert scope_response.status_code == 400, scope_response.text
    assert "scope/subject anchor" in scope_response.json()["error"]["message"]

    provenance_entry_id = _run(client, _seed_soft_deleted_provenance)
    provenance_response = client.post(
        f"/api/v1/entries/review/{provenance_entry_id}/accept"
    )
    assert provenance_response.status_code == 400, provenance_response.text
    assert "provenance.source_id" in provenance_response.json()["error"]["message"]


def test_review_edit_forbids_owner_and_status_fields(client) -> None:
    entry_id = _run(client, _seed_note, "no body owner or status")
    response = client.post(
        f"/api/v1/entries/review/{entry_id}/edit",
        json={
            "content": "attempted bypass",
            "user_id": "00000000-0000-0000-0000-000000000099",
            "status": "canon",
        },
    )
    assert response.status_code == 422, response.text
    errors = response.json()["error"]["details"]["errors"]
    assert {error["loc"][-1] for error in errors} == {"status", "user_id"}


def test_review_accept_does_not_take_owner_or_status_from_body(client) -> None:
    entry_id = _run(client, _seed_note, "authenticated context owns transition")
    response = client.post(
        f"/api/v1/entries/review/{entry_id}/accept",
        json={
            "user_id": "00000000-0000-0000-0000-000000000099",
            "status": "rejected",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["user_id"] == DEFAULT_USER_ID
    assert response.json()["status"] == EntryStatus.CANON.value


def test_review_api_requires_authentication_when_auth_is_enabled() -> None:
    from app.main import create_app

    settings = get_settings().model_copy(update={"AUTH_ENABLED": True})
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as unauthenticated:
        response = unauthenticated.get("/api/v1/entries/review")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
