"""RFC-002 Entry vocabulary and boundary validation tests."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

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


def _provenance(
    capture_method: ProvenanceCaptureMethod = ProvenanceCaptureMethod.HUMAN_AUTHORED,
) -> EntryProvenance:
    return EntryProvenance(
        source_kind=ProvenanceSourceKind.USER,
        capture_method=capture_method,
        producer="test-user",
    )


def test_entry_vocabularies_are_closed() -> None:
    assert {status.value for status in EntryStatus} == {
        "captured",
        "proposed",
        "canon",
        "rejected",
        "superseded",
    }
    assert "note" in {entry_type.value for entry_type in EntryType}
    assert "misc" not in {entry_type.value for entry_type in EntryType}

    with pytest.raises(ValidationError):
        EntryCreate(
            scope_kind=EntryScope.USER,
            type="misc",
            content="invalid type",
            provenance=_provenance(),
        )


def test_ai_extraction_cannot_use_captured_or_canon() -> None:
    for status in (EntryStatus.CAPTURED, EntryStatus.CANON):
        with pytest.raises(ValidationError, match="must start proposed"):
            EntryCreate(
                scope_kind=EntryScope.USER,
                type=EntryType.NOTE,
                status=status,
                content="AI candidate",
                provenance=_provenance(ProvenanceCaptureMethod.AI_EXTRACTED),
                confidence=0.8,
            )

    proposed = EntryCreate(
        scope_kind=EntryScope.USER,
        type=EntryType.NOTE,
        status=EntryStatus.PROPOSED,
        content="AI candidate",
        provenance=_provenance(ProvenanceCaptureMethod.AI_EXTRACTED),
        confidence=0.8,
    )
    assert proposed.status is EntryStatus.PROPOSED


def test_terminal_and_canon_statuses_cannot_be_created_directly() -> None:
    for status in (EntryStatus.CANON, EntryStatus.REJECTED, EntryStatus.SUPERSEDED):
        with pytest.raises(ValidationError, match=f"directly as {status.value}"):
            EntryCreate(
                scope_kind=EntryScope.USER,
                type=EntryType.NOTE,
                status=status,
                content="Invalid initial state",
                provenance=_provenance(),
            )


def test_confidence_and_priority_bounds_are_enforced() -> None:
    for confidence in (-0.01, 1.01):
        with pytest.raises(ValidationError):
            EntryCreate(
                scope_kind=EntryScope.USER,
                type=EntryType.NOTE,
                content="Invalid confidence",
                provenance=_provenance(),
                confidence=confidence,
            )
    for priority in (-1, 101):
        with pytest.raises(ValidationError):
            EntryCreate(
                scope_kind=EntryScope.USER,
                type=EntryType.NOTE,
                content="Invalid priority",
                provenance=_provenance(),
                priority=priority,
            )


def test_chat_private_and_invalid_subject_contracts_are_rejected() -> None:
    with pytest.raises(ValidationError, match="chat-private"):
        EntryCreate(
            scope_kind=EntryScope.CHAT_PRIVATE,
            scope_id="chat-id",
            type=EntryType.NOTE,
            content="private memory",
            provenance=_provenance(),
        )

    with pytest.raises(ValidationError, match="character subject"):
        EntryCreate(
            scope_kind=EntryScope.WORK,
            scope_id="work-id",
            subject_type=EntrySubjectType.WORK,
            subject_id="work-id",
            type=EntryType.CHARACTER_VOICE,
            content="voice",
            provenance=_provenance(),
        )
