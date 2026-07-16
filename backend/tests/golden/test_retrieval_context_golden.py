"""Golden regression coverage for the Phase 1 retrieve-to-context boundary."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.engines.prompt.entry_context import (
    ASSEMBLY_BUDGET_EXCLUSION,
    ASSEMBLY_POLICY_VERSION,
    ENTRY_STORE_SOURCE,
    EntryContextAssemblyRequest,
    assemble_entry_context,
)
from app.models.character import Character
from app.models.entry import Entry
from app.models.novel import Work
from app.models.user import User
from app.schemas.entry import EntryScope, EntryStatus, EntrySubjectType, EntryType
from app.services.entry_service import EntryService
from tests.golden.retrieval_context_fixture import (
    AI_NOTE_ID,
    ASSEMBLY_BUDGET,
    CONTEXT_EXPECTATION,
    DELETED_WORK_ID,
    EXEMPLAR_ID,
    HARIN_ID,
    ORPHAN_ID,
    OWNER_ID,
    REJECTED_ID,
    RELATIONSHIP_STATE_ID,
    RETRIEVAL_EXPECTATION,
    RETRIEVAL_POLICY_VERSION,
    SCORE_FACTOR_KEYS,
    STORY_FACT_ID,
    STORY_SUMMARY_ID,
    SUPERSEDED_ID,
    WORK_ID,
    frozen_retrieval_request,
)

NOW = datetime(2026, 7, 17, tzinfo=UTC)


@pytest.fixture()
async def golden_db(tmp_path):
    """Use only a per-test SQLite database; the repository root DB is untouched."""

    database = tmp_path / "phase1-bench-golden.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database.as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        yield sessionmaker, database
    finally:
        await engine.dispose()


def _entry(
    entry_id: str,
    *,
    content: str,
    title: str,
    entry_type: EntryType,
    priority: int,
    status: EntryStatus = EntryStatus.CANON,
    scope_id: str = WORK_ID,
    subject_type: EntrySubjectType | None = EntrySubjectType.WORK,
    subject_id: str | None = WORK_ID,
    provenance: dict[str, object] | None = None,
    confidence: float | None = None,
) -> Entry:
    return Entry(
        id=entry_id,
        user_id=OWNER_ID,
        scope_kind=EntryScope.WORK.value,
        scope_id=scope_id,
        subject_type=subject_type.value if subject_type is not None else None,
        subject_id=subject_id,
        subject_data={},
        type=entry_type.value,
        status=status.value,
        title=title,
        content=content,
        data={},
        provenance=provenance
        or {
            "source_kind": "chapter",
            "source_id": "bench-chapter-1",
            "capture_method": "human-authored",
            "producer": "phase1-bench-fixture",
        },
        confidence=confidence,
        priority=priority,
        accepted_at=NOW if status is EntryStatus.CANON else None,
        rejected_at=NOW if status is EntryStatus.REJECTED else None,
        superseded_at=NOW if status is EntryStatus.SUPERSEDED else None,
        created_at=NOW,
        updated_at=NOW,
    )


async def _seed_frozen_snapshot(session: AsyncSession) -> None:
    session.add_all(
        [
            User(id=OWNER_ID, email="bench-golden@example.com", display_name="Bench"),
            Work(id=WORK_ID, user_id=OWNER_ID, title="Golden work"),
            Work(
                id=DELETED_WORK_ID,
                user_id=OWNER_ID,
                title="Deleted golden work",
                deleted_at=NOW,
            ),
            Character(id=HARIN_ID, user_id=OWNER_ID, name="하린"),
        ]
    )
    await session.flush()
    session.add_all(
        [
            _entry(
                RELATIONSHIP_STATE_ID,
                title="하린과 준의 현재 거리",
                content="부두 단서를 공유했지만 하린은 준을 아직 믿지 않는다.",
                entry_type=EntryType.RELATIONSHIP_STATE,
                priority=85,
                subject_type=EntrySubjectType.CHARACTER,
                subject_id=HARIN_ID,
            ),
            _entry(
                STORY_FACT_ID,
                title="부두 창고의 열쇠",
                content="부두 창고의 열쇠는 하린이 숨긴 단서 상자 안에 있다.",
                entry_type=EntryType.STORY_FACT,
                priority=90,
            ),
            _entry(
                STORY_SUMMARY_ID,
                title="부두 장면 요약",
                content="부두 단서를 확인한 하린과 준은 창고 앞에서 서로의 목적을 의심한다. "
                "이 요약은 다음 장면의 긴장과 열쇠의 행방을 보존한다. "
                "두 사람은 새벽이 오기 전에 상자를 찾아야 한다.",
                entry_type=EntryType.STORY_SUMMARY,
                priority=80,
            ),
            _entry(
                EXEMPLAR_ID,
                title="준의 승인된 대사",
                content="부두 단서를 보며 준은 짧고 절제된 말투를 유지한다.",
                entry_type=EntryType.CHARACTER_EXEMPLAR,
                priority=30,
                subject_type=EntrySubjectType.CHARACTER,
                subject_id=HARIN_ID,
            ),
            _entry(
                AI_NOTE_ID,
                title="낮은 신뢰 메모",
                content="부두 단서가 오래된 약속과 연결될 수 있다는 추정.",
                entry_type=EntryType.NOTE,
                priority=20,
                provenance={
                    "source_kind": "chapter",
                    "source_id": "bench-chapter-1",
                    "capture_method": "ai-extracted",
                    "producer": "phase1-bench-fixture",
                },
                confidence=0.1,
            ),
            _entry(
                ORPHAN_ID,
                title="삭제된 작품의 단서",
                content="부두 단서는 삭제된 작품의 낡은 설정이다.",
                entry_type=EntryType.STORY_FACT,
                priority=100,
                scope_id=DELETED_WORK_ID,
                subject_id=DELETED_WORK_ID,
            ),
            _entry(
                REJECTED_ID,
                title="거절된 단서",
                content="부두 단서는 잘못된 진술이었다.",
                entry_type=EntryType.STORY_FACT,
                priority=100,
                status=EntryStatus.REJECTED,
            ),
            _entry(
                SUPERSEDED_ID,
                title="대체된 단서",
                content="부두 단서는 이미 대체된 옛 사실이다.",
                entry_type=EntryType.STORY_FACT,
                priority=100,
                status=EntryStatus.SUPERSEDED,
            ),
        ]
    )
    await session.commit()


@pytest.mark.asyncio
async def test_frozen_retrieval_snapshot_preserves_order_and_exclusion_trace(golden_db) -> None:
    sessionmaker, database = golden_db
    assert database.name == "phase1-bench-golden.db"
    assert database.resolve() != (Path(__file__).parents[2] / "data" / "app.db").resolve()
    async with sessionmaker() as session:
        await _seed_frozen_snapshot(session)
        result = await EntryService().retrieve(session, frozen_retrieval_request())

    assert result.policy_version == RETRIEVAL_POLICY_VERSION
    assert [item.entry.id for item in result.items] == RETRIEVAL_EXPECTATION.selected_entry_ids
    assert {
        item.entry.id: item.matched_terms for item in result.items
    } == RETRIEVAL_EXPECTATION.matched_terms
    assert result.trace.excluded_orphaned_entry_ids == RETRIEVAL_EXPECTATION.orphaned_entry_ids
    assert result.trace.budget_rejected_entry_ids == []
    assert result.trace.limit_rejected_entry_ids == RETRIEVAL_EXPECTATION.limit_rejected_entry_ids
    assert all(
        entry_id not in [item.entry.id for item in result.items]
        for entry_id in RETRIEVAL_EXPECTATION.excluded_by_default_entry_ids
    )
    assert all(
        set(item.score_breakdown.model_dump()) == SCORE_FACTOR_KEYS for item in result.items
    )
    assert [item.score for item in result.items] == sorted(
        (item.score for item in result.items), reverse=True
    )


@pytest.mark.asyncio
async def test_frozen_context_snapshot_preserves_blocks_metadata_and_separate_trace(golden_db) -> None:
    sessionmaker, _ = golden_db
    async with sessionmaker() as session:
        await _seed_frozen_snapshot(session)
        retrieval = await EntryService().retrieve(session, frozen_retrieval_request())

    assembled = assemble_entry_context(
        EntryContextAssemblyRequest(retrieval, budget=ASSEMBLY_BUDGET)
    )

    assert assembled.assembly_policy_version == ASSEMBLY_POLICY_VERSION
    assert assembled.source_retrieval_policy_version == RETRIEVAL_POLICY_VERSION
    assert assembled.included_entry_ids == CONTEXT_EXPECTATION.included_entry_ids
    assert assembled.assembly_excluded_entry_ids == CONTEXT_EXPECTATION.assembly_excluded_entry_ids
    assert [block.content for block in assembled.blocks] == CONTEXT_EXPECTATION.block_text
    assert assembled.requested_budget == CONTEXT_EXPECTATION.requested_budget
    assert assembled.budget_used == CONTEXT_EXPECTATION.used_budget
    assert [block.metadata["entry_id"] for block in assembled.blocks] == assembled.included_entry_ids
    assert [
        {key: block.metadata[key] for key in expectation}
        for block, expectation in zip(assembled.blocks, CONTEXT_EXPECTATION.metadata, strict=True)
    ] == CONTEXT_EXPECTATION.metadata
    assert all(block.metadata["source"] == ENTRY_STORE_SOURCE for block in assembled.blocks)
    assert all(block.metadata["policy_version"] == RETRIEVAL_POLICY_VERSION for block in assembled.blocks)
    assert all(
        block.metadata["assembly_policy_version"] == ASSEMBLY_POLICY_VERSION
        for block in assembled.blocks
    )
    assert assembled.trace.retrieval == retrieval.trace
    assert [exclusion.entry_id for exclusion in assembled.trace.assembly_exclusions] == [
        STORY_SUMMARY_ID
    ]
    assert assembled.trace.assembly_exclusions[0].reason == ASSEMBLY_BUDGET_EXCLUSION
    assert assembled.trace.assembly_exclusions[0].stage == "context_assembly"


@pytest.mark.asyncio
async def test_frozen_snapshot_is_deterministic_across_retrieval_and_assembly_reruns(golden_db) -> None:
    sessionmaker, _ = golden_db
    async with sessionmaker() as session:
        await _seed_frozen_snapshot(session)
        service = EntryService()
        first = await service.retrieve(session, frozen_retrieval_request())
        second = await service.retrieve(session, frozen_retrieval_request())

    first_context = assemble_entry_context(
        EntryContextAssemblyRequest(first, budget=ASSEMBLY_BUDGET)
    )
    second_context = assemble_entry_context(
        EntryContextAssemblyRequest(second, budget=ASSEMBLY_BUDGET)
    )

    assert first.model_dump() == second.model_dump()
    assert first_context == second_context
