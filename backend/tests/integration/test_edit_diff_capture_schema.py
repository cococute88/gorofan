"""Schema-level contract tests for `edit_diff_captures` (P1-7 design §8, §12).

These exercise the database constraints directly, because the constraints —
not the service layer — are what guarantee a capture row can never be
anchorless, duplicated, or silently orphaned.
"""
from __future__ import annotations

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base, utcnow
from app.models.edit_diff import EditDiffCapture
from app.models.entry import Entry
from app.models.novel import Chapter, Work
from app.models.user import User
from app.services.edit_diff_capture import (
    PAYLOAD_STATE_OVERSIZE,
    PAYLOAD_STATE_STORED,
    SOURCE_KIND_CHAPTER_CONTINUATION,
    SOURCE_KIND_ENTRY_REVIEW_EDIT,
    measure_side,
)


@pytest.fixture()
async def capture_db(tmp_path):
    database = tmp_path / "captures.db"
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


async def _seed(session: AsyncSession) -> tuple[User, Entry, Chapter]:
    user = User(email="capture@example.com", display_name="capture")
    session.add(user)
    await session.flush()
    entry = Entry(
        user_id=user.id,
        scope_kind="user",
        type="note",
        status="proposed",
        content="AI proposal",
        subject_data={},
        data={},
        provenance={
            "source_kind": "user",
            "capture_method": "ai-extracted",
            "producer": "test",
        },
        priority=50,
    )
    work = Work(user_id=user.id, title="work")
    session.add_all([entry, work])
    await session.flush()
    chapter = Chapter(work_id=work.id, user_id=user.id, index=1, title="ch")
    session.add(chapter)
    await session.commit()
    return user, entry, chapter


def _entry_capture(user_id: str, entry_id: str, *, sequence: int = 0) -> EditDiffCapture:
    before = measure_side("AI proposal")
    after = measure_side("human replacement")
    return EditDiffCapture(
        user_id=user_id,
        source_kind=SOURCE_KIND_ENTRY_REVIEW_EDIT,
        entry_id=entry_id,
        sequence=sequence,
        before_state=before.state,
        after_state=after.state,
        before_text=before.text,
        after_text=after.text,
        before_sha256=before.sha256,
        after_sha256=after.sha256,
        before_chars=before.chars,
        after_chars=after.chars,
        context={"fields_changed": ["content"]},
        settled_at=utcnow(),
    )


def _chapter_capture(
    user_id: str, chapter_id: str, *, sequence: int = 0, segment: str = "AI segment"
) -> EditDiffCapture:
    before = measure_side(segment)
    return EditDiffCapture(
        user_id=user_id,
        source_kind=SOURCE_KIND_CHAPTER_CONTINUATION,
        chapter_id=chapter_id,
        sequence=sequence,
        before_state=before.state,
        before_text=before.text,
        before_sha256=before.sha256,
        before_chars=before.chars,
        context={"insert_offset": 0, "chapter_version": 2},
        settled_at=None,
    )


@pytest.mark.asyncio
async def test_entry_and_chapter_anchored_rows_persist(capture_db) -> None:
    async with capture_db() as session:
        user, entry, chapter = await _seed(session)
        session.add(_entry_capture(user.id, entry.id))
        session.add(_chapter_capture(user.id, chapter.id))
        await session.commit()

        total = (
            await session.execute(select(func.count()).select_from(EditDiffCapture))
        ).scalar_one()
        assert total == 2


@pytest.mark.asyncio
async def test_a_capture_without_a_source_is_rejected(capture_db) -> None:
    async with capture_db() as session:
        user, _entry, _chapter = await _seed(session)
        orphan = _entry_capture(user.id, "unused")
        orphan.entry_id = None
        session.add(orphan)
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_a_capture_with_two_sources_is_rejected(capture_db) -> None:
    async with capture_db() as session:
        user, entry, chapter = await _seed(session)
        both = _entry_capture(user.id, entry.id)
        both.chapter_id = chapter.id
        session.add(both)
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_duplicate_sequence_per_source_is_rejected(capture_db) -> None:
    async with capture_db() as session:
        user, entry, _chapter = await _seed(session)
        session.add(_entry_capture(user.id, entry.id, sequence=0))
        await session.commit()
        session.add(_entry_capture(user.id, entry.id, sequence=0))
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_an_entry_capture_must_be_born_settled(capture_db) -> None:
    async with capture_db() as session:
        user, entry, _chapter = await _seed(session)
        unsettled = _entry_capture(user.id, entry.id)
        unsettled.after_state = None
        unsettled.after_text = None
        unsettled.after_sha256 = None
        unsettled.after_chars = None
        unsettled.settled_at = None
        session.add(unsettled)
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_an_oversize_unsettled_chapter_row_is_legal(capture_db) -> None:
    """Regression for the constraint defect the architecture review corrected.

    A Path B row whose AI segment exceeds the cap is written *both* oversize and
    not-yet-settled. A single `payload_state` column made this unrepresentable.
    """
    async with capture_db() as session:
        user, _entry, chapter = await _seed(session)
        oversize = _chapter_capture(user.id, chapter.id, segment="가" * 100_001)
        assert oversize.before_state == PAYLOAD_STATE_OVERSIZE
        assert oversize.before_text is None
        session.add(oversize)
        await session.commit()

        stored = (await session.execute(select(EditDiffCapture))).scalars().one()
        assert stored.before_state == PAYLOAD_STATE_OVERSIZE
        assert stored.before_text is None
        assert stored.before_chars == 100_001
        assert stored.before_sha256
        assert stored.after_state is None
        assert stored.settled_at is None


@pytest.mark.asyncio
async def test_oversize_text_must_be_null_not_truncated(capture_db) -> None:
    async with capture_db() as session:
        user, _entry, chapter = await _seed(session)
        lying = _chapter_capture(user.id, chapter.id)
        lying.before_state = PAYLOAD_STATE_OVERSIZE
        lying.before_text = "truncated prefix"
        session.add(lying)
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_a_stored_side_must_carry_its_text(capture_db) -> None:
    async with capture_db() as session:
        user, _entry, chapter = await _seed(session)
        empty = _chapter_capture(user.id, chapter.id)
        empty.before_state = PAYLOAD_STATE_STORED
        empty.before_text = None
        session.add(empty)
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_deleting_a_chapter_cascades_its_captures_away(capture_db) -> None:
    async with capture_db() as session:
        user, _entry, chapter = await _seed(session)
        session.add(_chapter_capture(user.id, chapter.id))
        await session.commit()

        # Mirrors NovelService.delete_chapter(): an ORM delete. With no
        # relationship declared, the database cascade is what runs; a
        # relationship without passive_deletes=True would null chapter_id and
        # leave the author's prose behind as an unattributable orphan.
        await session.delete(chapter)
        await session.commit()

        remaining = (
            await session.execute(select(func.count()).select_from(EditDiffCapture))
        ).scalar_one()
        assert remaining == 0


@pytest.mark.asyncio
async def test_deleting_an_entry_cascades_its_captures_away(capture_db) -> None:
    async with capture_db() as session:
        user, entry, _chapter = await _seed(session)
        session.add(_entry_capture(user.id, entry.id))
        await session.commit()

        await session.delete(entry)
        await session.commit()

        remaining = (
            await session.execute(select(func.count()).select_from(EditDiffCapture))
        ).scalar_one()
        assert remaining == 0


@pytest.mark.asyncio
async def test_deleting_a_user_cascades_every_capture_away(capture_db) -> None:
    async with capture_db() as session:
        user, entry, chapter = await _seed(session)
        session.add(_entry_capture(user.id, entry.id))
        session.add(_chapter_capture(user.id, chapter.id))
        await session.commit()

        await session.delete(user)
        await session.commit()

        remaining = (
            await session.execute(select(func.count()).select_from(EditDiffCapture))
        ).scalar_one()
        assert remaining == 0


def test_no_orm_relationship_targets_the_capture_table() -> None:
    """Deletion cascades stay at the database level (design §12, §20.25)."""
    for mapper in (Base.registry.mappers):
        for relationship in mapper.relationships:
            if relationship.mapper.class_ is EditDiffCapture:
                assert relationship.passive_deletes is True, (
                    f"{mapper.class_.__name__}.{relationship.key} would null the "
                    "capture foreign key instead of cascading"
                )
