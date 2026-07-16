"""Frozen Phase 1 retrieval-to-context fixture; not a runtime Bench feature.

The fixture deliberately records policy-facing expectations (IDs, ordering,
trace categories, and rendered text) rather than raw ranking scores.  It is a
small developer regression input for later ranking and context changes.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.schemas.entry import (
    EntryRetrievalTaskKind,
    EntryRetrieveRequest,
    EntryScope,
    EntryScopeSelector,
)

OWNER_ID = "bench-owner"
WORK_ID = "bench-work"
DELETED_WORK_ID = "bench-deleted-work"
HARIN_ID = "bench-character-harin"

RELATIONSHIP_STATE_ID = "bench-relationship-state"
STORY_FACT_ID = "bench-story-fact"
STORY_SUMMARY_ID = "bench-story-summary"
EXEMPLAR_ID = "bench-exemplar"
AI_NOTE_ID = "bench-ai-note"
ORPHAN_ID = "bench-orphaned-work-entry"
REJECTED_ID = "bench-rejected"
SUPERSEDED_ID = "bench-superseded"

RETRIEVAL_POLICY_VERSION = "entry-keyword-v1"
ASSEMBLY_POLICY_VERSION = "entry-prompt-block-v1"
RETRIEVAL_BUDGET = 2_000
RETRIEVAL_LIMIT = 3
# Fits the first two blocks but deliberately excludes the long summary block.
ASSEMBLY_BUDGET = 100
SCORE_FACTOR_KEYS = {
    "keyword",
    "identity",
    "type_weight",
    "status",
    "recency",
    "priority",
    "confidence",
    "authority",
    "exemplar",
}


@dataclass(frozen=True)
class RetrievalGoldenExpectation:
    selected_entry_ids: list[str]
    matched_terms: dict[str, list[str]]
    orphaned_entry_ids: list[str]
    limit_rejected_entry_ids: list[str]
    excluded_by_default_entry_ids: list[str]


@dataclass(frozen=True)
class ContextGoldenExpectation:
    included_entry_ids: list[str]
    assembly_excluded_entry_ids: list[str]
    block_text: list[str]
    metadata: list[dict[str, object]]
    requested_budget: int
    used_budget: int


RETRIEVAL_EXPECTATION = RetrievalGoldenExpectation(
    selected_entry_ids=[RELATIONSHIP_STATE_ID, STORY_FACT_ID, STORY_SUMMARY_ID],
    matched_terms={
        RELATIONSHIP_STATE_ID: ["단서", "부두"],
        STORY_FACT_ID: ["단서", "부두"],
        STORY_SUMMARY_ID: ["단서", "부두"],
    },
    orphaned_entry_ids=[ORPHAN_ID],
    limit_rejected_entry_ids=[EXEMPLAR_ID, AI_NOTE_ID],
    excluded_by_default_entry_ids=[REJECTED_ID, SUPERSEDED_ID],
)

CONTEXT_EXPECTATION = ContextGoldenExpectation(
    included_entry_ids=[RELATIONSHIP_STATE_ID, STORY_FACT_ID],
    assembly_excluded_entry_ids=[STORY_SUMMARY_ID],
    block_text=[
        "[relationship.state] 하린과 준의 현재 거리\n"
        "부두 단서를 공유했지만 하린은 준을 아직 믿지 않는다.",
        "[story.fact] 부두 창고의 열쇠\n"
        "부두 창고의 열쇠는 하린이 숨긴 단서 상자 안에 있다.",
    ],
    metadata=[
        {
            "entry_id": RELATIONSHIP_STATE_ID,
            "entry_type": "relationship.state",
            "entry_status": "canon",
            "scope_kind": "work",
            "scope_id": WORK_ID,
            "subject_type": "character",
            "subject_id": HARIN_ID,
            "matched_terms": ["단서", "부두"],
        },
        {
            "entry_id": STORY_FACT_ID,
            "entry_type": "story.fact",
            "entry_status": "canon",
            "scope_kind": "work",
            "scope_id": WORK_ID,
            "subject_type": "work",
            "subject_id": WORK_ID,
            "matched_terms": ["단서", "부두"],
        },
    ],
    requested_budget=ASSEMBLY_BUDGET,
    used_budget=75,
)


def frozen_retrieval_request() -> EntryRetrieveRequest:
    """Return the fixed situation used by the golden snapshot."""

    return EntryRetrieveRequest(
        user_id=OWNER_ID,
        scopes=[
            EntryScopeSelector(scope_kind=EntryScope.WORK, scope_id=WORK_ID),
            EntryScopeSelector(scope_kind=EntryScope.WORK, scope_id=DELETED_WORK_ID),
            # Chat-private selectors never expand a Store retrieval scope.
            EntryScopeSelector(scope_kind=EntryScope.CHAT_PRIVATE),
        ],
        cast=[HARIN_ID],
        beat="부두 단서",
        budget=RETRIEVAL_BUDGET,
        limit=RETRIEVAL_LIMIT,
        task_kind=EntryRetrievalTaskKind.CONTINUITY,
    )


# TODO(bench): add a Korean single-syllable recall scenario once a measured
# retrieval change is proposed. `_terms()` intentionally ignores terms of one
# character today; this fixture keeps that limitation visible without adding a
# speculative xfail or changing ranking constants.
KOREAN_SINGLE_SYLLABLE_RECALL_TODO = "봄"

# TODO(bench): add a dedicated competing-subject case before any ranking-tuning
# PR. Keyword overlap can dominate identity relevance; this fixture locks the
# current contract but does not call that trade-off correct or tune it here.
KEYWORD_DOMINANCE_TODO = "incidental prose overlap versus subject relevance"
