"""Pure Chapter-summary chronology policy shared by production and diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.entry import (
    EntryScope,
    EntryStatus,
    EntrySubjectType,
    StorySummaryChronologyAnchor,
    StorySummaryChronologyDisposition,
)


@dataclass(frozen=True)
class StorySummarySourceEvidence:
    """Already-read facts needed to classify one ``story.summary`` Entry."""

    scope_kind: str
    scope_id: str | None
    subject_type: str | None
    subject_id: str | None
    summary_level: object
    status: str
    superseded_by_entry_id: str | None
    source_chapter_id: str | None = None
    source_work_id: str | None = None
    source_chapter_index: int | None = None
    source_owner_id: str | None = None
    source_work_owner_id: str | None = None
    source_work_active: bool = False
    governed_same_source_valid: bool = True


@dataclass(frozen=True)
class StorySummaryClassification:
    disposition: StorySummaryChronologyDisposition
    reason: str
    source_chapter_id: str | None = None
    source_chapter_index: int | None = None

    @property
    def eligible(self) -> bool:
        return self.disposition is StorySummaryChronologyDisposition.PRIOR


def is_substantive_legacy_summary(summary: str) -> bool:
    """Return whether the NOT NULL legacy summary carries actual prose."""

    return bool(summary.strip())


def classify_chapter_story_position(
    *,
    target_chapter_id: str,
    target_chapter_index: int,
    source_chapter_id: str | None,
    source_chapter_index: int | None,
) -> StorySummaryClassification:
    """Classify already-validated same-Work Chapter identity and positions."""

    unknown = StorySummaryChronologyDisposition.UNKNOWN
    if source_chapter_id is None or source_chapter_index is None:
        return StorySummaryClassification(unknown, "orphan_source_chapter")
    if source_chapter_id == target_chapter_id:
        if source_chapter_index != target_chapter_index:
            return StorySummaryClassification(unknown, "source_consistency_failure")
        return StorySummaryClassification(
            StorySummaryChronologyDisposition.CURRENT,
            "current_chapter_summary",
            source_chapter_id,
            source_chapter_index,
        )
    if source_chapter_index == target_chapter_index:
        return StorySummaryClassification(
            unknown,
            "ambiguous_source_position",
            source_chapter_id,
            source_chapter_index,
        )
    disposition = (
        StorySummaryChronologyDisposition.PRIOR
        if source_chapter_index < target_chapter_index
        else StorySummaryChronologyDisposition.FUTURE
    )
    return StorySummaryClassification(
        disposition,
        (
            "eligible_prior_summary"
            if disposition is StorySummaryChronologyDisposition.PRIOR
            else "future_chapter_summary"
        ),
        source_chapter_id,
        source_chapter_index,
    )


def classify_story_summary(
    anchor: StorySummaryChronologyAnchor,
    source: StorySummarySourceEvidence,
) -> StorySummaryClassification:
    """Classify one summary without database access, ranking, or side effects."""

    unknown = StorySummaryChronologyDisposition.UNKNOWN
    if source.status != EntryStatus.CANON.value or source.superseded_by_entry_id is not None:
        return StorySummaryClassification(unknown, "invalid_lifecycle")
    if source.scope_kind != EntryScope.WORK.value:
        return StorySummaryClassification(unknown, "invalid_summary_scope")
    if source.scope_id != anchor.work_id:
        return StorySummaryClassification(unknown, "cross_work_scope")
    if source.subject_type != EntrySubjectType.CHAPTER.value or not source.subject_id:
        return StorySummaryClassification(unknown, "missing_chapter_subject")
    if source.summary_level not in {None, "chapter"}:
        return StorySummaryClassification(unknown, "unsupported_summary_level")
    if not source.governed_same_source_valid:
        return StorySummaryClassification(unknown, "governed_provenance_contradiction")
    if source.source_chapter_id is None:
        return StorySummaryClassification(unknown, "orphan_source_chapter")
    if source.source_owner_id != anchor.owner_id or source.source_work_owner_id != anchor.owner_id:
        return StorySummaryClassification(
            unknown,
            "foreign_source_chapter",
            source.source_chapter_id,
            None,
        )
    if not source.source_work_active:
        return StorySummaryClassification(
            unknown,
            "orphan_source_chapter",
            source.source_chapter_id,
            None,
        )
    if source.source_work_id != anchor.work_id:
        return StorySummaryClassification(
            unknown,
            "cross_work_source_chapter",
            source.source_chapter_id,
            None,
        )
    if source.source_chapter_index is None:
        return StorySummaryClassification(unknown, "orphan_source_chapter")
    if source.source_chapter_id != source.subject_id:
        return StorySummaryClassification(unknown, "source_consistency_failure")
    return classify_chapter_story_position(
        target_chapter_id=anchor.chapter_id,
        target_chapter_index=anchor.chapter_index,
        source_chapter_id=source.source_chapter_id,
        source_chapter_index=source.source_chapter_index,
    )
