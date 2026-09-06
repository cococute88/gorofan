"""Pure contract tests for Chapter-level story.summary chronology."""
from __future__ import annotations

import pytest

from app.schemas.entry import (
    StorySummaryChronologyAnchor,
    StorySummaryChronologyDisposition,
    StorySummaryGenerationOperation,
)
from app.services.story_summary_chronology import (
    StorySummarySourceEvidence,
    classify_story_summary,
    is_substantive_legacy_summary,
)


def _anchor() -> StorySummaryChronologyAnchor:
    return StorySummaryChronologyAnchor(
        owner_id="owner",
        work_id="work",
        chapter_id="chapter-3",
        chapter_index=3,
        operation=StorySummaryGenerationOperation.CONTINUE,
    )


def _source(**changes: object) -> StorySummarySourceEvidence:
    values: dict[str, object] = {
        "scope_kind": "work",
        "scope_id": "work",
        "subject_type": "chapter",
        "subject_id": "chapter-1",
        "summary_level": None,
        "status": "canon",
        "superseded_by_entry_id": None,
        "source_chapter_id": "chapter-1",
        "source_work_id": "work",
        "source_chapter_index": 1,
        "source_owner_id": "owner",
        "source_work_owner_id": "owner",
        "source_work_active": True,
        "governed_same_source_valid": True,
    }
    values.update(changes)
    return StorySummarySourceEvidence(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("source", "disposition", "reason"),
    [
        (_source(), StorySummaryChronologyDisposition.PRIOR, "eligible_prior_summary"),
        (
            _source(
                subject_id="chapter-3",
                source_chapter_id="chapter-3",
                source_chapter_index=3,
            ),
            StorySummaryChronologyDisposition.CURRENT,
            "current_chapter_summary",
        ),
        (
            _source(
                subject_id="chapter-7",
                source_chapter_id="chapter-7",
                source_chapter_index=7,
            ),
            StorySummaryChronologyDisposition.FUTURE,
            "future_chapter_summary",
        ),
        (
            _source(subject_type="work"),
            StorySummaryChronologyDisposition.UNKNOWN,
            "missing_chapter_subject",
        ),
        (
            _source(summary_level="arc"),
            StorySummaryChronologyDisposition.UNKNOWN,
            "unsupported_summary_level",
        ),
        (
            _source(source_chapter_id=None, source_chapter_index=None),
            StorySummaryChronologyDisposition.UNKNOWN,
            "orphan_source_chapter",
        ),
        (
            _source(source_owner_id="other"),
            StorySummaryChronologyDisposition.UNKNOWN,
            "foreign_source_chapter",
        ),
        (
            _source(source_work_id="other-work"),
            StorySummaryChronologyDisposition.UNKNOWN,
            "cross_work_source_chapter",
        ),
        (
            _source(governed_same_source_valid=False),
            StorySummaryChronologyDisposition.UNKNOWN,
            "governed_provenance_contradiction",
        ),
        (
            _source(status="superseded"),
            StorySummaryChronologyDisposition.UNKNOWN,
            "invalid_lifecycle",
        ),
        (
            _source(
                subject_id="chapter-other",
                source_chapter_id="chapter-other",
                source_chapter_index=3,
            ),
            StorySummaryChronologyDisposition.UNKNOWN,
            "ambiguous_source_position",
        ),
    ],
)
def test_classifier_is_fail_closed(
    source: StorySummarySourceEvidence,
    disposition: StorySummaryChronologyDisposition,
    reason: str,
) -> None:
    result = classify_story_summary(_anchor(), source)

    assert result.disposition is disposition
    assert result.reason == reason
    assert result.eligible is (disposition is StorySummaryChronologyDisposition.PRIOR)


@pytest.mark.parametrize("value", ["", "   ", "\n\r\n", "\t"])
def test_legacy_whitespace_is_not_substantive(value: str) -> None:
    assert is_substantive_legacy_summary(value) is False


def test_legacy_prose_is_substantive_without_rewriting_it() -> None:
    assert is_substantive_legacy_summary("  실제 요약  ") is True


@pytest.mark.parametrize("provenance_kind", ["user", "import", "reference"])
def test_generic_provenance_does_not_change_subject_chronology(
    provenance_kind: str,
) -> None:
    # created_at_chapter_id is deliberately absent from classifier evidence.
    # Generic user/import/reference provenance therefore cannot invent a
    # same-source invariant based on this optional field.
    result = classify_story_summary(_anchor(), _source())

    assert provenance_kind in {"user", "import", "reference"}
    assert result.disposition is StorySummaryChronologyDisposition.PRIOR
