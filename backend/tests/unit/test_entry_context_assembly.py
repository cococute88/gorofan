"""Contract tests for the Entry retrieval to PromptBlock bridge."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.engines.prompt.entry_context import (
    ASSEMBLY_BUDGET_EXCLUSION,
    ENTRY_STORE_SOURCE,
    EntryContextAssemblyRequest,
    assemble_entry_context,
    entry_retrieval_item_to_prompt_block,
    render_entry_prompt_text,
)
from app.engines.prompt.tokenizer import default_tokenizer
from app.schemas.entry import (
    EntryRead,
    EntryRetrievalItem,
    EntryRetrievalResult,
    EntryRetrievalScore,
    EntryRetrievalTrace,
    EntryScope,
    EntryStatus,
    EntrySubjectType,
    EntryType,
)

NOW = datetime(2026, 7, 13, tzinfo=UTC)


def _item(
    entry_id: str,
    *,
    content: str = "황궁의 비밀 통로는 북쪽 벽 뒤에 있다.",
    title: str | None = "비밀 통로",
    entry_type: EntryType = EntryType.STORY_FACT,
    scope_kind: EntryScope = EntryScope.WORK,
    scope_id: str | None = "work-1",
    subject_type: EntrySubjectType | None = EntrySubjectType.WORK,
    subject_id: str | None = "work-1",
    provenance: dict | None = None,
    confidence: float | None = 0.8,
    priority: int = 70,
    score: float = 2.75,
    matched_terms: list[str] | None = None,
    reason: list[str] | None = None,
    estimated_tokens: int | None = None,
) -> EntryRetrievalItem:
    entry = EntryRead(
        id=entry_id,
        user_id="owner",
        scope_kind=scope_kind,
        scope_id=scope_id,
        subject_type=subject_type,
        subject_id=subject_id,
        subject_data={},
        type=entry_type,
        status=EntryStatus.CANON,
        title=title,
        content=content,
        data={},
        provenance=(
            provenance
            if provenance is not None
            else {
                "source_kind": "chapter",
                "source_id": "chapter-1",
                "capture_method": "human-edited",
                "producer": "test",
            }
        ),
        confidence=confidence,
        priority=priority,
        created_at_chapter_id="chapter-1",
        superseded_by_entry_id=None,
        accepted_at=NOW,
        rejected_at=None,
        superseded_at=None,
        created_at=NOW,
        updated_at=NOW,
    )
    breakdown = EntryRetrievalScore(
        keyword=1.0,
        identity=0.4,
        type_weight=0.35,
        status=0.25,
        recency=0.2,
        priority=0.7,
        confidence=0.05,
        authority=0.0,
        exemplar=0.0,
    )
    return EntryRetrievalItem(
        entry=entry,
        score=score,
        matched_terms=matched_terms or ["비밀"],
        score_breakdown=breakdown,
        reason=reason or ["keyword", "type_weight"],
        estimated_tokens=(
            estimated_tokens
            if estimated_tokens is not None
            else default_tokenizer.count(content)
        ),
    )


def _result(
    items: list[EntryRetrievalItem],
    *,
    trace: EntryRetrievalTrace | None = None,
) -> EntryRetrievalResult:
    return EntryRetrievalResult(
        items=items,
        total_estimated_tokens=sum(item.estimated_tokens for item in items),
        requested_budget=4096,
        policy_version="entry-keyword-v1",
        trace=trace or EntryRetrievalTrace(),
    )


def test_selected_order_and_rendered_text_are_deterministic() -> None:
    items = [_item("entry-b", title="두 번째"), _item("entry-a", title="첫 번째")]
    retrieval = _result(items)

    first = assemble_entry_context(EntryContextAssemblyRequest(retrieval, budget=4096))
    second = assemble_entry_context(EntryContextAssemblyRequest(retrieval, budget=4096))

    assert first.included_entry_ids == ["entry-b", "entry-a"]
    assert [block.content for block in first.blocks] == [block.content for block in second.blocks]
    assert first.blocks[0].content == "[story.fact] 두 번째\n황궁의 비밀 통로는 북쪽 벽 뒤에 있다."


def test_metadata_preserves_entry_and_retrieval_trace_fields() -> None:
    item = _item("entry-1")
    block = entry_retrieval_item_to_prompt_block(
        item,
        policy_version="entry-keyword-v1",
    )

    assert block.metadata["entry_id"] == "entry-1"
    assert block.metadata["entry_type"] == "story.fact"
    assert block.metadata["entry_status"] == "canon"
    assert block.metadata["scope_kind"] == "work"
    assert block.metadata["scope_id"] == "work-1"
    assert block.metadata["subject_type"] == "work"
    assert block.metadata["subject_id"] == "work-1"
    assert block.metadata["retrieval_score"] == item.score
    assert block.metadata["retrieval_reason"] == item.reason
    assert block.metadata["matched_terms"] == item.matched_terms
    assert block.metadata["score_breakdown"] == item.score_breakdown.model_dump()
    assert block.metadata["provenance"] == item.entry.provenance
    assert block.metadata["confidence"] == item.entry.confidence
    assert block.metadata["priority"] == item.entry.priority
    assert block.metadata["source"] == ENTRY_STORE_SOURCE
    assert block.metadata["policy_version"] == "entry-keyword-v1"


def test_rendered_block_token_estimate_is_recalculated() -> None:
    item = _item("entry-1", content="짧은 사실", estimated_tokens=1)
    block = entry_retrieval_item_to_prompt_block(
        item,
        policy_version="entry-keyword-v1",
    )

    assert block.token_count == default_tokenizer.count(block.content)
    assert block.token_count > item.estimated_tokens
    assert block.metadata["rendered_estimated_tokens"] == block.token_count


def test_budget_excludes_whole_blocks_and_records_assembly_trace() -> None:
    first_item = _item("included", title="포함")
    excluded_item = _item("excluded", title="제외", content="긴 사실 " * 50)
    first_block = entry_retrieval_item_to_prompt_block(
        first_item,
        policy_version="entry-keyword-v1",
    )
    retrieval = _result([first_item, excluded_item])

    assembled = assemble_entry_context(
        EntryContextAssemblyRequest(retrieval, budget=first_block.token_count)
    )

    assert assembled.included_entry_ids == ["included"]
    assert assembled.assembly_excluded_entry_ids == ["excluded"]
    assert assembled.budget_used == first_block.token_count
    assert assembled.blocks[0].content == render_entry_prompt_text(first_item)
    assert assembled.blocks[0].truncatable is False
    exclusion = assembled.trace.assembly_exclusions[0]
    assert exclusion.entry_id == "excluded"
    assert exclusion.reason == ASSEMBLY_BUDGET_EXCLUSION
    assert exclusion.stage == "context_assembly"
    assert exclusion.budget_remaining == 0


def test_retrieval_and_assembly_budget_exclusions_remain_distinct() -> None:
    selected = _item("assembly-rejected", content="매우 긴 사실 " * 40)
    retrieval = _result(
        [selected],
        trace=EntryRetrievalTrace(
            excluded_orphaned_entry_ids=["orphaned"],
            budget_rejected_entry_ids=["retrieval-rejected"],
            limit_rejected_entry_ids=["limit-rejected"],
        ),
    )

    assembled = assemble_entry_context(EntryContextAssemblyRequest(retrieval, budget=1))

    assert assembled.trace.retrieval.budget_rejected_entry_ids == ["retrieval-rejected"]
    assert assembled.trace.retrieval.limit_rejected_entry_ids == ["limit-rejected"]
    assert assembled.trace.retrieval.excluded_orphaned_entry_ids == ["orphaned"]
    assert assembled.assembly_excluded_entry_ids == ["assembly-rejected"]


def test_empty_retrieval_does_not_synthesize_chat_private_context() -> None:
    assembled = assemble_entry_context(
        EntryContextAssemblyRequest(_result([]), budget=128)
    )

    assert assembled.blocks == []
    assert assembled.included_entry_ids == []
    assert assembled.assembly_excluded_entry_ids == []
    assert assembled.budget_used == 0
    assert assembled.source_retrieval_policy_version == "entry-keyword-v1"


def test_missing_title_provenance_and_confidence_are_preserved_safely() -> None:
    item = _item("minimal", title=None, provenance={}, confidence=None)
    block = entry_retrieval_item_to_prompt_block(
        item,
        policy_version="entry-keyword-v1",
    )

    assert block.content.startswith("[story.fact]\n")
    assert block.metadata["title"] is None
    assert block.metadata["provenance"] == {}
    assert block.metadata["confidence"] is None


@pytest.mark.parametrize("budget", [0, -1, True, 1.5])
def test_assembly_budget_is_required_positive_int(budget: object) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        EntryContextAssemblyRequest(_result([]), budget=budget)  # type: ignore[arg-type]


def test_assembly_converts_only_selected_items() -> None:
    item = _item(
        "user-preference",
        entry_type=EntryType.USER_PREFERENCE,
        scope_kind=EntryScope.USER,
        scope_id=None,
        subject_type=None,
        subject_id=None,
    )
    retrieval = _result(
        [item],
        trace=EntryRetrievalTrace(budget_rejected_entry_ids=["not-selected"]),
    )

    assembled = assemble_entry_context(EntryContextAssemblyRequest(retrieval, budget=4096))

    assert assembled.included_entry_ids == ["user-preference"]
    assert [block.metadata["scope_kind"] for block in assembled.blocks] == ["user"]
    assert all(block.metadata["scope_kind"] != "chat-private" for block in assembled.blocks)
