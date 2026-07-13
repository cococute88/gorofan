"""Entry Store DTOs and governed RFC-002 vocabularies."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import TimestampedOut


class EntryScope(StrEnum):
    USER = "user"
    COLLECTION = "collection"
    WORK = "work"
    CHARACTER = "character"
    WORLD = "world"
    CHAT_PRIVATE = "chat-private"


class EntryType(StrEnum):
    CHARACTER_IDENTITY = "character.identity"
    CHARACTER_BEHAVIOR = "character.behavior"
    CHARACTER_VOICE = "character.voice"
    CHARACTER_EXEMPLAR = "character.exemplar"
    WORLD_FACT = "world.fact"
    WORLD_TERM = "world.term"
    STORY_FACT = "story.fact"
    STORY_KNOWLEDGE = "story.knowledge"
    STORY_PROMISE = "story.promise"
    STORY_SUMMARY = "story.summary"
    RELATIONSHIP_STATE = "relationship.state"
    STYLE_PREFERENCE = "style.preference"
    USER_PREFERENCE = "user.preference"
    NOTE = "note"


class EntryStatus(StrEnum):
    CAPTURED = "captured"
    PROPOSED = "proposed"
    CANON = "canon"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class EntrySubjectType(StrEnum):
    WORK = "work"
    CHAPTER = "chapter"
    CHARACTER = "character"
    WORLD = "world"
    CHARACTER_PAIR = "character-pair"


class ProvenanceSourceKind(StrEnum):
    USER = "user"
    REFERENCE = "reference"
    CHAPTER = "chapter"
    CHAT_BOOKMARK = "chat-bookmark"
    EDIT_DIFF = "edit-diff"
    IMPORT = "import"


class ProvenanceCaptureMethod(StrEnum):
    HUMAN_AUTHORED = "human-authored"
    AI_EXTRACTED = "ai-extracted"
    HUMAN_EDITED = "human-edited"
    IMPORTED = "imported"


class EntryProvenance(BaseModel):
    source_kind: ProvenanceSourceKind
    source_id: str | None = None
    locator: dict[str, Any] = Field(default_factory=dict)
    capture_method: ProvenanceCaptureMethod
    producer: str = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def require_stable_internal_source(self) -> Self:
        if self.source_kind in {
            ProvenanceSourceKind.CHAPTER,
            ProvenanceSourceKind.CHAT_BOOKMARK,
            ProvenanceSourceKind.EDIT_DIFF,
        } and not self.source_id:
            raise ValueError(f"{self.source_kind.value} provenance requires source_id")
        return self


class EntryCreate(BaseModel):
    scope_kind: EntryScope
    scope_id: str | None = None
    subject_type: EntrySubjectType | None = None
    subject_id: str | None = None
    subject_data: dict[str, Any] = Field(default_factory=dict)
    type: EntryType
    status: EntryStatus = EntryStatus.CAPTURED
    title: str | None = Field(default=None, max_length=300)
    content: str = Field(min_length=1)
    data: dict[str, Any] = Field(default_factory=dict)
    provenance: EntryProvenance
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    priority: int = Field(default=50, ge=0, le=100)
    created_at_chapter_id: str | None = None

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("content must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_contract(self) -> Self:
        if self.scope_kind is EntryScope.CHAT_PRIVATE:
            raise ValueError("chat-private Memory cannot be persisted as an Entry in Phase 1")
        if self.scope_kind is EntryScope.USER:
            if self.scope_id is not None:
                raise ValueError("user scope uses the implicit owner and cannot have scope_id")
        elif not self.scope_id:
            raise ValueError(f"{self.scope_kind.value} scope requires scope_id")

        if self.subject_type is None:
            if self.subject_id is not None or self.subject_data:
                raise ValueError("subject_id/subject_data require subject_type")
        elif self.subject_type is EntrySubjectType.CHARACTER_PAIR:
            character_ids = self.subject_data.get("character_ids")
            if not isinstance(character_ids, list) or len(character_ids) != 2:
                raise ValueError("character-pair subject requires two character_ids")
            if len(set(character_ids)) != 2 or not all(isinstance(item, str) for item in character_ids):
                raise ValueError("character-pair character_ids must be two distinct strings")
        elif not self.subject_id:
            raise ValueError(f"{self.subject_type.value} subject requires subject_id")

        if self.type.value.startswith("character.") and self.subject_type is not EntrySubjectType.CHARACTER:
            raise ValueError("character.* entries require a character subject")
        if self.type in {EntryType.WORLD_FACT, EntryType.WORLD_TERM} and not (
            self.subject_type is EntrySubjectType.WORLD
            or (self.subject_type is None and self.scope_kind is EntryScope.WORLD)
        ):
            raise ValueError("world.* entries require a world subject or world scope")
        if self.type is EntryType.STORY_KNOWLEDGE and not (
            self.scope_kind is EntryScope.WORK
            and self.subject_type is EntrySubjectType.CHARACTER
        ):
            raise ValueError("story.knowledge requires work scope and a character subject")
        if self.type is EntryType.STORY_FACT and not (
            self.scope_kind is EntryScope.WORK
            and self.subject_type
            in {None, EntrySubjectType.WORK, EntrySubjectType.CHAPTER}
        ):
            raise ValueError("story.fact requires work scope and an optional work/chapter subject")
        if self.type is EntryType.STORY_PROMISE and not (
            self.scope_kind is EntryScope.WORK
            and self.subject_type in {None, EntrySubjectType.WORK}
        ):
            raise ValueError("story.promise requires work scope and an optional work subject")
        if self.type is EntryType.STORY_SUMMARY and not (
            self.scope_kind is EntryScope.WORK
            and self.subject_type in {EntrySubjectType.WORK, EntrySubjectType.CHAPTER}
        ):
            raise ValueError("story.summary requires work scope and a work/chapter subject")
        if self.type is EntryType.RELATIONSHIP_STATE and not (
            self.scope_kind is EntryScope.WORK
            and self.subject_type is EntrySubjectType.CHARACTER_PAIR
        ):
            raise ValueError("relationship.state requires work scope and a character-pair subject")
        if self.type is EntryType.USER_PREFERENCE and self.scope_kind is not EntryScope.USER:
            raise ValueError("user.preference requires user scope")
        if self.type is EntryType.STYLE_PREFERENCE and self.scope_kind not in {
            EntryScope.USER,
            EntryScope.COLLECTION,
            EntryScope.WORK,
        }:
            raise ValueError("style.preference requires user, collection, or work scope")

        if self.provenance.capture_method is ProvenanceCaptureMethod.AI_EXTRACTED:
            if self.status is not EntryStatus.PROPOSED:
                raise ValueError("AI-extracted entries must start proposed; captured cannot bypass review")
            if self.confidence is None:
                raise ValueError("AI-extracted entries require confidence")
        if self.status in {
            EntryStatus.CANON,
            EntryStatus.REJECTED,
            EntryStatus.SUPERSEDED,
        }:
            raise ValueError(f"entries cannot be created directly as {self.status.value}")
        return self


class EntryUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    content: str | None = Field(default=None, min_length=1)
    data: dict[str, Any] | None = None
    provenance: EntryProvenance | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    priority: int | None = Field(default=None, ge=0, le=100)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("content must not be blank")
        return normalized


class EntryRead(TimestampedOut):
    user_id: str
    scope_kind: EntryScope
    scope_id: str | None
    subject_type: EntrySubjectType | None
    subject_id: str | None
    subject_data: dict[str, Any]
    type: EntryType
    status: EntryStatus
    title: str | None
    content: str
    data: dict[str, Any]
    provenance: dict[str, Any]
    confidence: float | None
    priority: int
    created_at_chapter_id: str | None
    superseded_by_entry_id: str | None
    accepted_at: datetime | None
    rejected_at: datetime | None
    superseded_at: datetime | None


class EntryRetrievalTaskKind(StrEnum):
    GENERAL = "general"
    SCENE = "scene"
    CONTINUITY = "continuity"
    VOICE = "voice"
    DIALOGUE = "dialogue"
    CHAT = "chat"


class EntryScopeSelector(BaseModel):
    scope_kind: EntryScope
    scope_id: str | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        if self.scope_kind in {EntryScope.USER, EntryScope.CHAT_PRIVATE}:
            if self.scope_id is not None:
                raise ValueError(f"{self.scope_kind.value} scope cannot have scope_id")
        elif not self.scope_id:
            raise ValueError(f"{self.scope_kind.value} scope requires scope_id")
        return self


class EntrySubjectFilter(BaseModel):
    subject_type: EntrySubjectType
    subject_id: str | None = None
    character_ids: list[str] = Field(default_factory=list, min_length=0, max_length=2)

    @model_validator(mode="after")
    def validate_subject(self) -> Self:
        if self.subject_type is EntrySubjectType.CHARACTER_PAIR:
            if len(self.character_ids) != 2 or len(set(self.character_ids)) != 2:
                raise ValueError("character-pair filter requires two distinct character_ids")
            if self.subject_id is not None:
                raise ValueError("character-pair filter derives subject_id from character_ids")
            self.character_ids = sorted(self.character_ids)
        elif not self.subject_id:
            raise ValueError(f"{self.subject_type.value} filter requires subject_id")
        elif self.character_ids:
            raise ValueError("character_ids are only valid for character-pair filters")
        return self

    @property
    def persisted_subject_id(self) -> str:
        if self.subject_type is EntrySubjectType.CHARACTER_PAIR:
            return "|".join(self.character_ids)
        assert self.subject_id is not None
        return self.subject_id


class EntryRetrieveRequest(BaseModel):
    """Internal owner-authorized Store retrieval situation (RFC-003).

    ``user_id`` is required by the service contract. An HTTP/API adapter must
    inject it from the authenticated context rather than accept it from a
    request body.
    """

    user_id: str = Field(
        min_length=1,
        description="Authenticated owner injected by the calling boundary",
    )
    scopes: list[EntryScopeSelector] = Field(min_length=1)
    cast: list[str] = Field(default_factory=list)
    location: str | None = None
    beat: str | None = None
    budget: int = Field(ge=1)
    entry_types: list[EntryType] | None = Field(default=None, min_length=1)
    subject_filters: list[EntrySubjectFilter] = Field(default_factory=list)
    status_filters: list[EntryStatus] | None = Field(default=None, min_length=1)
    include_superseded: bool = False
    include_rejected: bool = False
    task_kind: EntryRetrievalTaskKind = EntryRetrievalTaskKind.GENERAL
    limit: int = Field(default=20, ge=1, le=100)


class EntryRetrievalScore(BaseModel):
    keyword: float
    identity: float
    type_weight: float
    status: float
    recency: float
    priority: float
    confidence: float
    authority: float
    exemplar: float


class EntryRetrievalItem(BaseModel):
    entry: EntryRead
    score: float
    matched_terms: list[str]
    score_breakdown: EntryRetrievalScore
    reason: list[str]
    estimated_tokens: int
    truncated: bool = False


class EntryRetrievalTrace(BaseModel):
    excluded_orphaned_entry_ids: list[str] = Field(default_factory=list)
    budget_rejected_entry_ids: list[str] = Field(default_factory=list)
    limit_rejected_entry_ids: list[str] = Field(default_factory=list)


class EntryRetrievalResult(BaseModel):
    items: list[EntryRetrievalItem]
    total_estimated_tokens: int
    requested_budget: int
    policy_version: str
    truncated: bool = False
    trace: EntryRetrievalTrace
