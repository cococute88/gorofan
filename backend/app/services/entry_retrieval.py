"""Pure ranking and whole-Entry budget selection for RFC-003 retrieval."""
from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from app.engines.prompt.tokenizer import Tokenizer, default_tokenizer
from app.models.entry import Entry
from app.schemas.entry import (
    EntryRead,
    EntryRetrievalItem,
    EntryRetrievalScore,
    EntryRetrievalTaskKind,
    EntryRetrieveRequest,
    EntryType,
    StorySummaryChronologyEvidence,
)

RETRIEVAL_POLICY_VERSION = "entry-keyword-v2"
NEUTRAL_CONFIDENCE = 0.5
HUMAN_AUTHORITY_WEIGHT = 0.31
CONFIDENCE_FACTOR_MULTIPLIER = 0.6

_STATUS_WEIGHT = {
    "canon": 0.25,
    "captured": 0.0,
    "proposed": 0.0,
    "rejected": -0.25,
    "superseded": -0.25,
}
_BASE_TYPE_WEIGHT = {
    "story.fact": 0.35,
    "story.knowledge": 0.35,
    "story.promise": 0.35,
    "story.summary": 0.25,
    "relationship.state": 0.35,
    "character.identity": 0.25,
    "character.behavior": 0.2,
    "character.voice": 0.25,
    "character.exemplar": 0.25,
    "world.fact": 0.25,
    "world.term": 0.25,
    "style.preference": 0.15,
    "user.preference": 0.15,
    "note": 0.0,
}
_TASK_TYPE_BOOST: dict[EntryRetrievalTaskKind, dict[str, float]] = {
    EntryRetrievalTaskKind.SCENE: {
        "story.fact": 0.35,
        "story.knowledge": 0.4,
        "story.promise": 0.4,
        "relationship.state": 0.4,
        "character.identity": 0.25,
        "world.fact": 0.25,
    },
    EntryRetrievalTaskKind.CONTINUITY: {
        "story.fact": 0.6,
        "story.knowledge": 0.6,
        "story.promise": 0.6,
        "relationship.state": 0.5,
        "story.summary": 0.35,
    },
    EntryRetrievalTaskKind.VOICE: {
        "character.voice": 0.7,
        "character.behavior": 0.35,
        "character.identity": 0.25,
    },
    EntryRetrievalTaskKind.DIALOGUE: {
        "character.voice": 0.7,
        "character.behavior": 0.35,
        "relationship.state": 0.3,
    },
    EntryRetrievalTaskKind.CHAT: {
        "character.voice": 0.7,
        "character.identity": 0.4,
        "relationship.state": 0.3,
        "world.fact": 0.2,
    },
}
_VOICE_TASKS = {
    EntryRetrievalTaskKind.VOICE,
    EntryRetrievalTaskKind.DIALOGUE,
    EntryRetrievalTaskKind.CHAT,
}


@dataclass(frozen=True)
class RankedEntry:
    item: EntryRetrievalItem
    applicable_confidence: float
    chronology: float


def normalize_keyword_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _terms(request: EntryRetrieveRequest) -> list[str]:
    text = " ".join(part for part in (request.beat, request.location) if part)
    normalized = normalize_keyword_text(text)
    return sorted({term for term in re.findall(r"[^\W_]+", normalized) if len(term) > 1})


def _chronology(entry: Entry) -> float:
    value: datetime = entry.updated_at or entry.created_at
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.timestamp()


def _capture_method(entry: Entry) -> str | None:
    value = entry.provenance or {}
    method = value.get("capture_method")
    return method if isinstance(method, str) else None


def _confidence_factor(entry: Entry) -> tuple[float, float]:
    if _capture_method(entry) != "ai-extracted" or entry.confidence is None:
        return 0.0, NEUTRAL_CONFIDENCE
    return (
        (entry.confidence - NEUTRAL_CONFIDENCE) * CONFIDENCE_FACTOR_MULTIPLIER,
        entry.confidence,
    )


def _authority_factor(entry: Entry) -> float:
    return (
        HUMAN_AUTHORITY_WEIGHT
        if _capture_method(entry) in {"human-authored", "human-edited"}
        else 0.0
    )


def _identity_score(entry: Entry, request: EntryRetrieveRequest) -> float:
    raw_character_ids = (entry.subject_data or {}).get("character_ids", [])
    subject_ids = (
        {value for value in raw_character_ids if isinstance(value, str)}
        if isinstance(raw_character_ids, list)
        else set()
    )
    if entry.subject_id:
        subject_ids.add(entry.subject_id)
    cast_hits = sum(1 for character_id in set(request.cast) if character_id in subject_ids)
    location_hit = bool(
        request.location
        and request.location in {entry.scope_id, entry.subject_id}
    )
    return min(1.0, cast_hits * 0.4 + (0.4 if location_hit else 0.0))


def rank_entries(
    entries: list[Entry],
    request: EntryRetrieveRequest,
    *,
    tokenizer: Tokenizer = default_tokenizer,
    story_summary_chronology_by_entry_id: Mapping[
        str, StorySummaryChronologyEvidence
    ] | None = None,
) -> list[RankedEntry]:
    terms = _terms(request)
    summary_chronology = story_summary_chronology_by_entry_id or {}
    database_chronology = {
        entry.id: _chronology(entry)
        for entry in entries
        if entry.id not in summary_chronology
    }
    oldest = min(database_chronology.values(), default=0.0)
    newest = max(database_chronology.values(), default=0.0)
    span = newest - oldest
    task_weights = _TASK_TYPE_BOOST.get(request.task_kind, {})
    ranked: list[RankedEntry] = []

    for entry in entries:
        summary_evidence = summary_chronology.get(entry.id)
        searchable = normalize_keyword_text(
            " ".join(
                [
                    entry.title or "",
                    entry.content,
                    json.dumps(entry.data or {}, ensure_ascii=False, sort_keys=True),
                    json.dumps(entry.subject_data or {}, ensure_ascii=False, sort_keys=True),
                ]
            )
        )
        matched = [term for term in terms if term in searchable]
        keyword = (len(matched) / len(terms) * 4.0) if terms else 0.0
        identity = _identity_score(entry, request)
        type_weight = _BASE_TYPE_WEIGHT.get(entry.type, 0.0) + task_weights.get(
            entry.type, 0.0
        )
        status = _STATUS_WEIGHT.get(entry.status, 0.0)
        recency = (
            0.0
            if summary_evidence is not None
            else (
                (database_chronology[entry.id] - oldest) / span * 0.5
                if span
                else 0.0
            )
        )
        priority = entry.priority / 100.0
        confidence, applicable_confidence = _confidence_factor(entry)
        authority = _authority_factor(entry)
        exemplar = (
            1.0
            if request.task_kind in _VOICE_TASKS and entry.type == "character.exemplar"
            else 0.0
        )
        breakdown = EntryRetrievalScore(
            keyword=round(keyword, 6),
            identity=round(identity, 6),
            type_weight=round(type_weight, 6),
            status=round(status, 6),
            recency=round(recency, 6),
            priority=round(priority, 6),
            confidence=round(confidence, 6),
            authority=round(authority, 6),
            exemplar=round(exemplar, 6),
        )
        score = round(sum(breakdown.model_dump().values()), 6)
        reasons = [name for name, value in breakdown.model_dump().items() if value > 0]
        ranked.append(
            RankedEntry(
                item=EntryRetrievalItem(
                    entry=EntryRead.model_validate(entry),
                    score=score,
                    matched_terms=matched,
                    score_breakdown=breakdown,
                    reason=reasons or ["eligible"],
                    estimated_tokens=tokenizer.count(entry.content),
                    story_summary_chronology=summary_evidence,
                ),
                applicable_confidence=applicable_confidence,
                chronology=(
                    float(summary_evidence.source_chapter_index)
                    if summary_evidence is not None
                    else database_chronology[entry.id]
                ),
            )
        )

    return sorted(
        ranked,
        key=lambda candidate: (
            -candidate.item.score,
            -candidate.item.entry.priority,
            -candidate.applicable_confidence,
            -candidate.chronology,
            candidate.item.entry.id,
        ),
    )


def order_selected_story_summaries(
    selected: list[EntryRetrievalItem],
) -> list[EntryRetrievalItem]:
    """Order summary survivors by story position without moving other types."""

    summary_slots = [
        index
        for index, item in enumerate(selected)
        if item.entry.type is EntryType.STORY_SUMMARY
    ]
    ordered_summaries = sorted(
        (selected[index] for index in summary_slots),
        key=lambda item: (
            item.story_summary_chronology.source_chapter_index
            if item.story_summary_chronology is not None
            else 0
        ),
    )
    ordered = list(selected)
    for index, item in zip(summary_slots, ordered_summaries, strict=True):
        ordered[index] = item
    return ordered


def select_entries(
    ranked: list[RankedEntry], request: EntryRetrieveRequest
) -> tuple[list[EntryRetrievalItem], list[str], list[str]]:
    selected: list[EntryRetrievalItem] = []
    budget_rejected: list[str] = []
    limit_rejected: list[str] = []
    used = 0
    for index, candidate in enumerate(ranked):
        if len(selected) >= request.limit:
            limit_rejected.extend(
                remaining.item.entry.id for remaining in ranked[index:]
            )
            break
        item = candidate.item
        if used + item.estimated_tokens > request.budget:
            budget_rejected.append(item.entry.id)
            continue
        selected.append(item)
        used += item.estimated_tokens
    return selected, budget_rejected, limit_rejected
