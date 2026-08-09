"""Path A — Review Card edit capture (P1-7 design §6.2, §17).

These drive the real `EntryService` write path and the real HTTP endpoint. A
test that constructs capture rows by hand would pass with the capture call
deleted from production code; `test_removing_the_capture_call_breaks_this_suite`
below pins that these do not.
"""
from __future__ import annotations

import hashlib
from functools import partial

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from app.config import get_settings
from app.db.base import Base
from app.models.edit_diff import EditDiffCapture
from app.models.entry import Entry
from app.models.user import User
from app.schemas.entry import (
    EntryAuthoringCreate,
    EntryCreate,
    EntryProvenance,
    EntryReviewEdit,
    EntryScope,
    EntryStatus,
    EntryType,
    ProvenanceCaptureMethod,
    ProvenanceSourceKind,
)
from app.services.edit_diff_capture import (
    PAYLOAD_STATE_OVERSIZE,
    PAYLOAD_STATE_STORED,
    SOURCE_KIND_ENTRY_REVIEW_EDIT,
)
from app.services.entry_service import EntryService

AI_PROPOSAL = "그녀는 존댓말을 쓰지 않는다."
HUMAN_REPLACEMENT = "그녀는 아무에게도 존댓말을 쓰지 않는다. 예외는 없다."


@pytest.fixture()
async def review_db(tmp_path):
    database = tmp_path / "review.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database.as_posix()}")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_conn, _record):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        yield sessionmaker
    finally:
        await engine.dispose()


def _ai_provenance() -> EntryProvenance:
    return EntryProvenance(
        source_kind=ProvenanceSourceKind.USER,
        capture_method=ProvenanceCaptureMethod.AI_EXTRACTED,
        producer="analyst.extract.v1",
    )


async def _seed_owner(session: AsyncSession) -> User:
    user = User(email="path-a@example.com", display_name="path a")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _seed_proposal(
    service: EntryService, session: AsyncSession, user_id: str, content: str
) -> Entry:
    return await service.create(
        session,
        user_id,
        EntryCreate(
            scope_kind=EntryScope.USER,
            type=EntryType.NOTE,
            status=EntryStatus.PROPOSED,
            title="AI title",
            content=content,
            data={"n": 1},
            provenance=_ai_provenance(),
            confidence=0.8,
        ),
    )


async def _captures(session: AsyncSession) -> list[EditDiffCapture]:
    stmt = select(EditDiffCapture).order_by(EditDiffCapture.sequence)
    return list((await session.execute(stmt)).scalars().all())


async def _capture_count(session: AsyncSession) -> int:
    return (
        await session.execute(select(func.count()).select_from(EditDiffCapture))
    ).scalar_one()


@pytest.mark.asyncio
async def test_content_edit_captures_the_pristine_ai_pre_image(review_db) -> None:
    service = EntryService()
    async with review_db() as session:
        owner = await _seed_owner(session)
        entry = await _seed_proposal(service, session, owner.id, AI_PROPOSAL)

        await service.edit_review_entry(
            session,
            owner.id,
            entry.id,
            EntryReviewEdit(content=HUMAN_REPLACEMENT),
        )

        rows = await _captures(session)
        assert len(rows) == 1
        capture = rows[0]
        assert capture.source_kind == SOURCE_KIND_ENTRY_REVIEW_EDIT
        assert capture.entry_id == entry.id
        assert capture.chapter_id is None
        assert capture.user_id == owner.id
        assert capture.sequence == 0
        assert capture.before_text == AI_PROPOSAL
        assert capture.after_text == HUMAN_REPLACEMENT
        assert capture.before_state == PAYLOAD_STATE_STORED
        assert capture.after_state == PAYLOAD_STATE_STORED
        assert capture.before_sha256 == hashlib.sha256(
            AI_PROPOSAL.encode("utf-8")
        ).hexdigest()
        assert capture.after_sha256 == hashlib.sha256(
            HUMAN_REPLACEMENT.encode("utf-8")
        ).hexdigest()
        # Code points, not bytes — the Korean text is multi-byte in UTF-8.
        assert capture.before_chars == len(AI_PROPOSAL)
        assert capture.after_chars == len(HUMAN_REPLACEMENT)
        assert capture.before_chars != len(AI_PROPOSAL.encode("utf-8"))
        # A Path A row is born settled; both sides exist at INSERT time.
        assert capture.settled_at is not None
        assert capture.producer == "analyst.extract.v1"
        assert capture.context == {"fields_changed": ["content"]}


@pytest.mark.asyncio
async def test_identical_content_writes_no_row(review_db) -> None:
    service = EntryService()
    async with review_db() as session:
        owner = await _seed_owner(session)
        entry = await _seed_proposal(service, session, owner.id, AI_PROPOSAL)

        await service.edit_review_entry(
            session, owner.id, entry.id, EntryReviewEdit(content=AI_PROPOSAL)
        )
        # A replayed identical request is inert for the same reason.
        await service.edit_review_entry(
            session, owner.id, entry.id, EntryReviewEdit(content=AI_PROPOSAL)
        )

        assert await _capture_count(session) == 0


@pytest.mark.asyncio
async def test_metadata_only_edit_writes_no_text_pair(review_db) -> None:
    service = EntryService()
    async with review_db() as session:
        owner = await _seed_owner(session)
        entry = await _seed_proposal(service, session, owner.id, AI_PROPOSAL)

        await service.edit_review_entry(
            session,
            owner.id,
            entry.id,
            EntryReviewEdit(title="Human title", data={"n": 2}),
        )

        assert await _capture_count(session) == 0
        refreshed = await service.get(session, owner.id, entry.id)
        assert refreshed.title == "Human title"


@pytest.mark.asyncio
async def test_second_edit_appends_a_row_and_keeps_the_original(review_db) -> None:
    service = EntryService()
    async with review_db() as session:
        owner = await _seed_owner(session)
        entry = await _seed_proposal(service, session, owner.id, AI_PROPOSAL)

        await service.edit_review_entry(
            session, owner.id, entry.id, EntryReviewEdit(content=HUMAN_REPLACEMENT)
        )
        await service.edit_review_entry(
            session, owner.id, entry.id, EntryReviewEdit(content="최종본입니다.")
        )

        rows = await _captures(session)
        assert [row.sequence for row in rows] == [0, 1]
        assert rows[0].before_text == AI_PROPOSAL
        assert rows[0].after_text == HUMAN_REPLACEMENT
        assert rows[1].before_text == HUMAN_REPLACEMENT
        assert rows[1].after_text == "최종본입니다."


@pytest.mark.asyncio
async def test_an_oversize_side_stores_null_text_and_never_a_prefix(review_db) -> None:
    service = EntryService()
    async with review_db() as session:
        owner = await _seed_owner(session)
        entry = await _seed_proposal(service, session, owner.id, AI_PROPOSAL)
        huge = "가" * 100_001

        await service.edit_review_entry(
            session, owner.id, entry.id, EntryReviewEdit(content=huge)
        )

        capture = (await _captures(session))[0]
        # Sides are decided independently.
        assert capture.before_state == PAYLOAD_STATE_STORED
        assert capture.before_text == AI_PROPOSAL
        assert capture.after_state == PAYLOAD_STATE_OVERSIZE
        assert capture.after_text is None
        assert capture.after_chars == 100_001
        assert capture.after_sha256 == hashlib.sha256(huge.encode("utf-8")).hexdigest()


@pytest.mark.asyncio
async def test_accept_reject_supersede_and_authoring_capture_nothing(review_db) -> None:
    service = EntryService()
    async with review_db() as session:
        owner = await _seed_owner(session)

        accepted = await _seed_proposal(service, session, owner.id, "수락될 제안")
        await service.accept_review_entry(session, owner.id, accepted.id)

        rejected = await _seed_proposal(service, session, owner.id, "거절될 제안")
        await service.reject_review_entry(session, owner.id, rejected.id)

        replacement = await _seed_proposal(service, session, owner.id, "교체본")
        await service.supersede(session, owner.id, accepted.id, replacement.id)

        await service.create_user_authored(
            session,
            owner.id,
            EntryAuthoringCreate(
                scope_kind=EntryScope.USER,
                type=EntryType.NOTE,
                content="사람이 직접 쓴 캐논",
            ),
        )

        assert await _capture_count(session) == 0


@pytest.mark.asyncio
async def test_capture_failure_rolls_the_edit_back(review_db, monkeypatch) -> None:
    """Tier 1 is atomic: no capture, no edit. The AI original must survive."""
    service = EntryService()
    async with review_db() as session:
        owner_id = (await _seed_owner(session)).id
        entry_id = (await _seed_proposal(service, session, owner_id, AI_PROPOSAL)).id

        async def _boom(*_args, **_kwargs):
            raise RuntimeError("induced capture failure")

        monkeypatch.setattr(service.captures, "capture_entry_review_edit", _boom)

        with pytest.raises(RuntimeError):
            await service.edit_review_entry(
                session, owner_id, entry_id, EntryReviewEdit(content=HUMAN_REPLACEMENT)
            )
        await session.rollback()

        preserved = await service.get(session, owner_id, entry_id)
        assert preserved.content == AI_PROPOSAL
        assert preserved.provenance["capture_method"] == "ai-extracted"
        assert await _capture_count(session) == 0


@pytest.mark.asyncio
async def test_capture_insert_failure_rolls_the_edit_back(review_db, monkeypatch) -> None:
    """The same guarantee when the failure is the INSERT itself, not the call."""
    service = EntryService()
    async with review_db() as session:
        owner_id = (await _seed_owner(session)).id
        entry_id = (await _seed_proposal(service, session, owner_id, AI_PROPOSAL)).id

        async def _boom(*_args, **_kwargs):
            raise RuntimeError("induced INSERT failure")

        monkeypatch.setattr(service.captures.repo, "add", _boom)

        with pytest.raises(RuntimeError):
            await service.edit_review_entry(
                session, owner_id, entry_id, EntryReviewEdit(content=HUMAN_REPLACEMENT)
            )
        await session.rollback()

        preserved = await service.get(session, owner_id, entry_id)
        assert preserved.content == AI_PROPOSAL
        assert await _capture_count(session) == 0


@pytest.mark.asyncio
async def test_captures_are_isolated_per_owner(review_db) -> None:
    service = EntryService()
    async with review_db() as session:
        owner = await _seed_owner(session)
        other = User(email="other@example.com", display_name="other")
        session.add(other)
        await session.commit()

        entry = await _seed_proposal(service, session, owner.id, AI_PROPOSAL)
        await service.edit_review_entry(
            session, owner.id, entry.id, EntryReviewEdit(content=HUMAN_REPLACEMENT)
        )

        rows = await _captures(session)
        assert [row.user_id for row in rows] == [owner.id]

        foreign = (
            await session.execute(
                select(func.count())
                .select_from(EditDiffCapture)
                .where(EditDiffCapture.user_id == other.id)
            )
        ).scalar_one()
        assert foreign == 0


def _run(client, function, *args, **kwargs):
    assert client.portal is not None
    return client.portal.call(
        partial(function, client.app.state.sessionmaker, *args, **kwargs)
    )


async def _seed_api_proposal(sessionmaker, content: str) -> str:
    user_id = get_settings().DEFAULT_USER_ID
    async with sessionmaker() as session:
        if await session.get(User, user_id) is None:
            session.add(
                User(id=user_id, email=f"{user_id}@capture.test", display_name="owner")
            )
            await session.commit()
        entry = await EntryService().create(
            session,
            user_id,
            EntryCreate(
                scope_kind=EntryScope.USER,
                type=EntryType.NOTE,
                status=EntryStatus.PROPOSED,
                content=content,
                provenance=_ai_provenance(),
                confidence=0.8,
            ),
        )
        return entry.id


async def _api_captures(sessionmaker, entry_id: str) -> list[EditDiffCapture]:
    async with sessionmaker() as session:
        stmt = (
            select(EditDiffCapture)
            .where(EditDiffCapture.entry_id == entry_id)
            .order_by(EditDiffCapture.sequence)
        )
        return list((await session.execute(stmt)).scalars().all())


def test_the_real_review_edit_endpoint_captures(client: TestClient) -> None:
    entry_id = _run(client, _seed_api_proposal, "API가 제안한 원문")

    response = client.post(
        f"/api/v1/entries/review/{entry_id}/edit",
        json={"content": "사람이 고친 본문"},
    )
    assert response.status_code == 200
    assert response.json()["content"] == "사람이 고친 본문"
    # P1-7 adds no API surface: the capture is invisible to the response.
    assert "edit_diff" not in response.text
    assert "before_text" not in response.text

    rows = _run(client, _api_captures, entry_id)
    assert len(rows) == 1
    assert rows[0].before_text == "API가 제안한 원문"
    assert rows[0].after_text == "사람이 고친 본문"

    # Accepting afterwards adds nothing — accept is a P1-9 audit fact.
    assert client.post(f"/api/v1/entries/review/{entry_id}/accept").status_code == 200
    assert len(_run(client, _api_captures, entry_id)) == 1


def test_removing_the_capture_call_breaks_this_suite() -> None:
    """Guards against a vacuous suite: the production call must be reachable.

    The mutation check itself is run manually (delete the call, watch these
    tests fail). This pins the call site so it cannot be quietly renamed into
    something the tests no longer exercise.
    """
    import inspect

    source = inspect.getsource(EntryService.edit_review_entry)
    assert "capture_entry_review_edit" in source
    assert "except Exception" not in source
