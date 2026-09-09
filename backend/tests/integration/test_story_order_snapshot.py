"""Actual SQLite snapshot regression for the T10/S2 -> T3/S4 reorder."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.config import Settings
from app.db.base import Base
from app.db.session import create_engine, create_sessionmaker
from app.models.entry import Entry
from app.models.novel import Chapter, Work
from app.models.user import User
from app.schemas.entry import StorySummaryGenerationOperation
from app.services.entry_generation_context import build_novel_retrieve_request
from app.services.entry_service import EntryService
from app.services.story_order_snapshot import begin_story_order_snapshot


@pytest.mark.asyncio
async def test_sqlite_snapshot_never_mixes_cached_target_with_fresh_source(
    tmp_path,
) -> None:
    database = tmp_path / "story-order-snapshot.db"
    settings = Settings(
        DATABASE_URL=f"sqlite+aiosqlite:///{database.as_posix()}"
    )
    engine = create_engine(settings)
    sessionmaker = create_sessionmaker(engine)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with sessionmaker() as seed:
        owner = User(email="snapshot@example.com", display_name="snapshot")
        seed.add(owner)
        await seed.flush()
        work = Work(user_id=owner.id, title="Snapshot")
        seed.add(work)
        await seed.flush()
        source = Chapter(
            work_id=work.id,
            user_id=owner.id,
            index=2,
            title="S",
            summary="legacy source",
        )
        target = Chapter(work_id=work.id, user_id=owner.id, index=10, title="T")
        seed.add_all([source, target])
        await seed.flush()
        summary = Entry(
            user_id=owner.id,
            scope_kind="work",
            scope_id=work.id,
            subject_type="chapter",
            subject_id=source.id,
            subject_data={},
            type="story.summary",
            status="canon",
            content="entry source",
            data={"level": "chapter"},
            provenance={
                "source_kind": "user",
                "capture_method": "human-authored",
                "producer": "snapshot-test",
            },
            priority=100,
        )
        seed.add(summary)
        await seed.commit()
        owner_id = owner.id
        work_id = work.id
        source_id = source.id
        target_id = target.id

    try:
        async with sessionmaker() as preparation:
            await begin_story_order_snapshot(preparation)
            target_before = await preparation.get(Chapter, target_id)
            assert target_before is not None
            assert target_before.index == 10

            async with sessionmaker() as reorder:
                reordered = list(
                    (
                        await reorder.execute(
                            select(Chapter).where(Chapter.work_id == work_id)
                        )
                    ).scalars().all()
                )
                for chapter in reordered:
                    chapter.index += 100000
                await reorder.flush()
                by_id = {chapter.id: chapter for chapter in reordered}
                by_id[target_id].index = 3
                by_id[source_id].index = 4
                await reorder.commit()

            rows = list(
                (
                    await preparation.execute(
                        select(Chapter)
                        .where(Chapter.work_id == work_id)
                        .order_by(Chapter.index)
                    )
                ).scalars().all()
            )
            assert [(chapter.id, chapter.index) for chapter in rows] == [
                (source_id, 2),
                (target_id, 10),
            ]
            request = build_novel_retrieve_request(
                user_id=owner_id,
                work=SimpleNamespace(id=work_id),
                world=None,
                characters=[],
                chapter=target_before,
                instruction="continue",
                context_window=8192,
                operation=StorySummaryGenerationOperation.CONTINUE,
                substantive_legacy_summary_chapter_ids=(source_id,),
            )
            result = await EntryService().retrieve(preparation, request)
            # The Entry overlaps substantive legacy in the accepted pre-reorder
            # view. It is excluded, never misclassified from target=10/source=4.
            assert result.items == []
            exclusion = result.trace.story_summary_chronology_exclusions[0]
            assert exclusion.reason == "legacy_summary_authority_overlap"
            assert exclusion.source_chapter_index == 2

        async with sessionmaker() as after:
            post = list(
                (
                    await after.execute(
                        select(Chapter)
                        .where(Chapter.work_id == work_id)
                        .order_by(Chapter.index)
                    )
                ).scalars().all()
            )
            assert [(chapter.id, chapter.index) for chapter in post] == [
                (target_id, 3),
                (source_id, 4),
            ]
    finally:
        await engine.dispose()
