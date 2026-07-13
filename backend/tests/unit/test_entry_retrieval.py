"""Pure ranking and budget tests for RFC-003 retrieval."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.engines.prompt.tokenizer import default_tokenizer
from app.models.entry import Entry
from app.schemas.entry import (
    EntryRetrievalTaskKind,
    EntryRetrieveRequest,
    EntryScope,
    EntryScopeSelector,
)
from app.services.entry_retrieval import (
    CONFIDENCE_FACTOR_MULTIPLIER,
    HUMAN_AUTHORITY_WEIGHT,
    NEUTRAL_CONFIDENCE,
    rank_entries,
    select_entries,
)


def _entry(
    entry_id: str,
    *,
    content: str = "same content",
    priority: int = 50,
    confidence: float | None = None,
    capture_method: str = "human-authored",
    updated_at: datetime | None = None,
) -> Entry:
    timestamp = updated_at or datetime(2026, 1, 1, tzinfo=UTC)
    return Entry(
        id=entry_id,
        user_id="owner",
        scope_kind="user",
        scope_id=None,
        subject_data={},
        type="note",
        status="canon",
        content=content,
        data={},
        provenance={
            "source_kind": "user",
            "capture_method": capture_method,
            "producer": "ranking-test",
        },
        confidence=confidence,
        priority=priority,
        created_at=timestamp,
        updated_at=timestamp,
    )


def _request(*, budget: int, **updates) -> EntryRetrieveRequest:
    return EntryRetrieveRequest(
        user_id="owner",
        scopes=[EntryScopeSelector(scope_kind=EntryScope.USER)],
        budget=budget,
        limit=20,
        **updates,
    )


def test_retrieval_budget_is_required_and_positive() -> None:
    values = {
        "user_id": "owner",
        "scopes": [EntryScopeSelector(scope_kind=EntryScope.USER)],
    }
    with pytest.raises(ValidationError, match="budget"):
        EntryRetrieveRequest(**values)
    with pytest.raises(ValidationError, match="valid integer"):
        EntryRetrieveRequest(**values, budget=None)
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        EntryRetrieveRequest(**values, budget=0)


def test_human_authority_weight_exceeds_max_confidence_bonus() -> None:
    """Confidence alone must never outrank explicit human authority."""
    max_confidence_bonus = (
        1.0 - NEUTRAL_CONFIDENCE
    ) * CONFIDENCE_FACTOR_MULTIPLIER
    assert HUMAN_AUTHORITY_WEIGHT > max_confidence_bonus


def test_priority_confidence_and_recency_are_deterministic_ranking_signals() -> None:
    old = datetime(2026, 1, 1, tzinfo=UTC)
    new = datetime(2026, 1, 2, tzinfo=UTC)

    priority_ranked = rank_entries(
        [
            _entry("low-priority", priority=0, updated_at=new),
            _entry("high-priority", priority=100, updated_at=old),
        ],
        _request(budget=4096),
    )
    assert priority_ranked[0].item.entry.id == "high-priority"

    confidence_ranked = rank_entries(
        [
            _entry("low-confidence", confidence=0.1, capture_method="ai-extracted"),
            _entry("high-confidence", confidence=0.9, capture_method="ai-extracted"),
        ],
        _request(budget=4096),
    )
    assert confidence_ranked[0].item.entry.id == "high-confidence"

    recency_ranked = rank_entries(
        [
            _entry("older", updated_at=old),
            _entry("newer", updated_at=new),
        ],
        _request(budget=4096),
    )
    assert recency_ranked[0].item.entry.id == "newer"


def test_missing_and_neutral_confidence_have_zero_effect() -> None:
    ranked = rank_entries(
        [
            _entry("missing", confidence=None, capture_method="ai-extracted"),
            _entry("neutral", confidence=0.5, capture_method="ai-extracted"),
        ],
        _request(budget=4096),
    )
    by_id = {candidate.item.entry.id: candidate.item for candidate in ranked}
    assert by_id["missing"].score_breakdown.confidence == 0.0
    assert by_id["neutral"].score_breakdown.confidence == 0.0
    assert by_id["missing"].score == by_id["neutral"].score

    authority_ranked = rank_entries(
        [
            _entry("human", capture_method="human-authored"),
            _entry("ai-maximum", confidence=1.0, capture_method="ai-extracted"),
        ],
        _request(budget=4096),
    )
    assert authority_ranked[0].item.entry.id == "human"


def test_keyword_match_and_stable_id_tie_break() -> None:
    keyword_ranked = rank_entries(
        [
            _entry("miss", content="winter palace"),
            _entry("match", content="황궁의 비밀 통로"),
        ],
        _request(budget=4096, beat="황궁 비밀"),
    )
    assert keyword_ranked[0].item.entry.id == "match"

    tied = rank_entries([_entry("b"), _entry("a")], _request(budget=4096))
    assert [candidate.item.entry.id for candidate in tied] == ["a", "b"]


def test_budget_selects_whole_entries_and_skips_oversize_candidates() -> None:
    oversized = _entry("oversized", content="비밀 " * 80, priority=100)
    small = _entry("small", content="짧은 사실", priority=10)
    budget = default_tokenizer.count(small.content)
    request = _request(beat="비밀", budget=budget)

    selected, budget_rejected, limit_rejected = select_entries(
        rank_entries([oversized, small], request), request
    )

    assert [item.entry.id for item in selected] == ["small"]
    assert selected[0].entry.content == small.content
    assert selected[0].truncated is False
    assert budget_rejected == ["oversized"]
    assert limit_rejected == []
    assert sum(item.estimated_tokens for item in selected) <= budget


def test_exemplar_boost_only_applies_to_voice_related_tasks() -> None:
    exemplar = _entry("exemplar")
    exemplar.type = "character.exemplar"
    general = rank_entries([exemplar], _request(budget=4096))
    voice = rank_entries(
        [exemplar], _request(budget=4096, task_kind=EntryRetrievalTaskKind.VOICE)
    )
    assert general[0].item.score_breakdown.exemplar == 0.0
    assert voice[0].item.score_breakdown.exemplar == 1.0


def test_cast_and_location_are_identity_hints_not_scope_expansion() -> None:
    cast_entry = _entry("cast")
    cast_entry.subject_type = "character"
    cast_entry.subject_id = "character-1"
    location_entry = _entry("location")
    location_entry.scope_kind = "world"
    location_entry.scope_id = "world-1"
    unrelated = _entry("unrelated")

    ranked = rank_entries(
        [unrelated, location_entry, cast_entry],
        _request(budget=4096, cast=["character-1"], location="world-1"),
    )

    assert {candidate.item.entry.id for candidate in ranked[:2]} == {"cast", "location"}
    assert ranked[0].item.score_breakdown.identity > 0
    assert ranked[1].item.score_breakdown.identity > 0
