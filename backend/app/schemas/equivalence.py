"""Typed P1-8 legacy-to-Entry diagnostic API contract."""
from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CoverageState(StrEnum):
    AMBIGUOUS_MATCH = "ambiguous_match"
    EQUIVALENT = "equivalent"
    CONTENT_MISMATCH = "content_mismatch"
    INELIGIBLE_ONLY = "ineligible_only"
    MISSING_ENTRY = "missing_entry"


class RuntimeState(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    EQUIVALENT = "equivalent"
    SELECTION_MISMATCH = "selection_mismatch"
    UNSUPPORTED_LEGACY_SEMANTICS = "unsupported_legacy_semantics"


class ProjectionKind(StrEnum):
    CHARACTER_PERSONALITY = "character_personality"
    CHARACTER_SPEECH_STYLE = "character_speech_style"
    WORLD_DESCRIPTION = "world_description"
    WORLD_ERA = "world_era"
    WORLD_RACE = "world_race"
    WORLD_NATION = "world_nation"
    WORLD_TABOO = "world_taboo"
    GLOSSARY_TERM = "glossary_term"
    LORE = "lore"
    CHAPTER_SUMMARY = "chapter_summary"


class ChatDiagnosticMode(StrEnum):
    NEW_MESSAGE = "new_message"
    REGENERATE = "regenerate"


class DiagnosticBudgetOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_window: int = Field(ge=256)
    max_tokens: int = Field(ge=1)
    safety_ratio: float = Field(ge=0.0, le=0.5)

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        if self.context_window < self.max_tokens:
            raise ValueError("context_window must be >= max_tokens")
        return self


class ChatEquivalenceSituation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chat_id: str = Field(min_length=1)
    mode: ChatDiagnosticMode
    user_message: str | None = None

    @field_validator("user_message")
    @classmethod
    def normalize_message(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            raise ValueError("user_message must not be blank")
        return value

    @model_validator(mode="after")
    def validate_mode(self) -> Self:
        if self.mode is ChatDiagnosticMode.NEW_MESSAGE and self.user_message is None:
            raise ValueError("new_message requires user_message")
        if self.mode is ChatDiagnosticMode.REGENERATE and self.user_message is not None:
            raise ValueError("regenerate forbids user_message")
        return self


class NovelEquivalenceSituation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_id: str = Field(min_length=1)
    instruction: str = ""
    target_words: int = Field(default=800, ge=50, le=5000)


class EquivalenceCompareRequest(BaseModel):
    """Exactly one authenticated concrete runtime situation."""

    model_config = ConfigDict(extra="forbid")

    chat: ChatEquivalenceSituation | None = None
    novel: NovelEquivalenceSituation | None = None
    budget_override: DiagnosticBudgetOverride | None = None

    @model_validator(mode="after")
    def exactly_one_situation(self) -> Self:
        if (self.chat is None) == (self.novel is None):
            raise ValueError("exactly one of chat or novel is required")
        return self


class PayloadSummary(BaseModel):
    sha256: str
    preview: str
    normalized_length: int
    title_sha256: str | None = None
    title_preview: str | None = None
    title_normalized_length: int | None = None


class ProjectionSelectionEvidence(BaseModel):
    aggregate_name: str | None = None
    keywords: list[str] = Field(default_factory=list)
    entry_enabled: bool | None = None
    lorebook_enabled: bool | None = None
    lorebook_id: str | None = None
    scan_depth: int | None = None
    effective_scan_depth: int | None = None
    history_count: int | None = None
    chapter_index: int | None = None


class ProjectionEvidence(BaseModel):
    source_key: str
    source_kind: str
    source_id: str
    source_field: str
    source_order: int
    projection_kind: ProjectionKind
    scope_kind: str
    scope_id: str
    subject_type: str
    subject_id: str
    entry_type: str
    expected: PayloadSummary
    priority: int | None = None
    story_position: int | None = None
    runtime_visibility: str
    selection_metadata: ProjectionSelectionEvidence = Field(
        default_factory=ProjectionSelectionEvidence
    )


class CandidateEvidence(BaseModel):
    entry_id: str
    status: str
    live_anchor: bool
    exact_payload: bool
    priority: int
    differing_fields: list[str] = Field(default_factory=list)
    payload: PayloadSummary
    subject_story_position: int | None = None
    created_at_chapter_position: int | None = None


class CoverageRecord(BaseModel):
    projection: ProjectionEvidence
    coverage_state: CoverageState
    eligible_exact_entry_ids: list[str] = Field(default_factory=list)
    ineligible_exact_entry_ids: list[str] = Field(default_factory=list)
    candidates: list[CandidateEvidence] = Field(default_factory=list)
    diagnostic_codes: list[str] = Field(default_factory=list)


class CoverageReport(BaseModel):
    records: list[CoverageRecord]
    blank_source_keys: list[str] = Field(default_factory=list)
    counts: dict[str, int]


class RuntimeSelectionEvidence(BaseModel):
    selected: bool
    selection_position: int | None = None
    retrieval_selected: bool | None = None
    assembly_selected: bool | None = None
    final_prompt_selected: bool | None = None
    exclusion_code: str | None = None
    trace_ids: list[str] = Field(default_factory=list)


class RuntimeRecord(BaseModel):
    source_key: str | None = None
    entry_id: str | None = None
    runtime_state: RuntimeState
    legacy: RuntimeSelectionEvidence
    entry: RuntimeSelectionEvidence
    diagnostic_codes: list[str] = Field(default_factory=list)


class RuntimeReport(BaseModel):
    surface: Literal["chat", "novel"]
    records: list[RuntimeRecord]
    counts: dict[str, int]


class EntryOnlyEvidence(BaseModel):
    entry_id: str
    scope_kind: str
    scope_id: str | None
    subject_type: str | None
    subject_id: str | None
    entry_type: str
    payload: PayloadSummary
    runtime_selected: bool
    diagnostic_codes: list[str] = Field(default_factory=list)


class SituationEvidence(BaseModel):
    kind: Literal["chat", "novel"]
    anchor_id: str
    mode: str | None = None
    context_window: int
    max_tokens: int
    safety_ratio: float
    budget_source: Literal["model_config", "diagnostic_override"]
    entry_context_feature_enabled: bool
    retrieval_policy_version: str
    assembly_policy_version: str
    projection_policy_version: str


class EquivalenceDiagnosticReport(BaseModel):
    situation: SituationEvidence
    coverage: CoverageReport
    runtime: RuntimeReport
    entry_only: list[EntryOnlyEvidence]
