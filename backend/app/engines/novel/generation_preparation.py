"""Provider-neutral, deterministic preparation for Chapter continuation.

The preparation layer snapshots already-authorized domain context into an
immutable runtime value.  It does not query the database, decide chronology,
render provider DTOs, or invoke a provider.  The existing ``PromptEngine``
remains responsible for final block ordering and the whole-prompt budget.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from app.engines.prompt.blocks import BlockKind, BlockRole, PromptBlock

CURRENT_CHAPTER_TAIL_CHARS = 1200
DEFAULT_CONTINUATION_INSTRUCTION = "자연스럽게 다음 장면을 이어써라."


class GenerationOperation(StrEnum):
    CONTINUE = "continue"


class GenerationSectionKind(StrEnum):
    STORY = "story"
    CHARACTERS = "characters"
    RELATIONSHIPS = "relationships"
    CANON_CONTEXT = "canon_context"
    PRIOR_CHAPTER_SUMMARIES = "prior_chapter_summaries"
    CURRENT_CHAPTER = "current_chapter"
    INSTRUCTION = "instruction"
    CONSTRAINTS = "constraints"


SECTION_ORDER = tuple(GenerationSectionKind)

# Only metadata required to identify, classify, validate, and order a selected
# Entry crosses the preparation boundary. Retrieval scores, provenance payloads,
# locators, and any caller-added values remain upstream.
ENTRY_BLOCK_METADATA_KEYS = frozenset(
    {
        "source",
        "entry_id",
        "entry_type",
        "scope_kind",
        "scope_id",
        "story_summary_chronology",
    }
)
STORY_SUMMARY_CHRONOLOGY_KEYS = frozenset(
    {"disposition", "source_chapter_id", "source_chapter_index"}
)


@dataclass(frozen=True)
class FrozenMap:
    """Recursively immutable, deterministically ordered JSON-like mapping."""

    items: tuple[tuple[str, object], ...] = ()

    def get(self, key: str, default: object = None) -> object:
        return next((value for name, value in self.items if name == key), default)


def freeze_mapping(value: Mapping[str, object] | None) -> FrozenMap:
    return FrozenMap(
        tuple(
            (str(key), _freeze_value(item))
            for key, item in sorted((value or {}).items(), key=lambda pair: str(pair[0]))
        )
    )


def thaw_mapping(value: FrozenMap) -> dict[str, object]:
    return {key: _thaw_value(item) for key, item in value.items}


def _freeze_value(value: object) -> object:
    if isinstance(value, Mapping):
        return freeze_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Preparation evidence must be JSON-like, got {type(value).__name__}")


def _thaw_value(value: object) -> object:
    if isinstance(value, FrozenMap):
        return thaw_mapping(value)
    if isinstance(value, tuple):
        return [_thaw_value(item) for item in value]
    return value


@dataclass(frozen=True)
class GenerationTarget:
    owner_id: str
    work_id: str
    chapter_id: str
    operation: GenerationOperation = GenerationOperation.CONTINUE


@dataclass(frozen=True)
class PreparedWorkContext:
    id: str
    owner_id: str
    title: str
    synopsis: str
    genre: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class PreparedCharacterContext:
    id: str
    owner_id: str
    name: str
    personality: str
    speech_style: str


@dataclass(frozen=True)
class PreparedWorldContext:
    id: str
    owner_id: str
    name: str
    description: str
    era: str


@dataclass(frozen=True)
class PreparedLoreContext:
    id: str
    content: str
    keywords: tuple[str, ...]
    priority: int
    scan_depth: int
    enabled: bool = True


@dataclass(frozen=True)
class PreparedChapterContext:
    id: str
    work_id: str
    owner_id: str
    index: int
    title: str
    tail: str


@dataclass(frozen=True)
class PreparedPriorSummary:
    chapter_id: str
    work_id: str
    chapter_index: int
    content: str


@dataclass(frozen=True)
class PreparedPromptBlock:
    """Whitelisted compatibility snapshot for the existing PromptEngine."""

    id: str
    role: BlockRole
    kind: BlockKind
    content: str
    priority: int
    token_count: int
    truncatable: bool
    metadata: FrozenMap

    @classmethod
    def from_prompt_block(cls, block: PromptBlock) -> PreparedPromptBlock:
        metadata = {
            key: value
            for key, value in block.metadata.items()
            if key in ENTRY_BLOCK_METADATA_KEYS
        }
        chronology = metadata.get("story_summary_chronology")
        if isinstance(chronology, Mapping):
            metadata["story_summary_chronology"] = {
                key: value
                for key, value in chronology.items()
                if key in STORY_SUMMARY_CHRONOLOGY_KEYS
            }
        return cls(
            id=block.id,
            role=block.role,
            kind=block.kind,
            content=block.content,
            priority=block.priority,
            token_count=block.token_count,
            truncatable=block.truncatable,
            metadata=freeze_mapping(metadata),
        )

    def to_prompt_block(self) -> PromptBlock:
        return PromptBlock(
            id=self.id,
            role=self.role,
            kind=self.kind,
            content=self.content,
            priority=self.priority,
            token_count=self.token_count,
            truncatable=self.truncatable,
            metadata=thaw_mapping(self.metadata),
        )


@dataclass(frozen=True)
class GenerationConstraint:
    name: Literal["target_words", "response_language", "continuation_mode"]
    value: str | int


@dataclass(frozen=True)
class GenerationSourceEvidence:
    section: GenerationSectionKind
    source_type: str
    source_id: str
    selection_order: int
    selected: bool = True
    reason: str = "selected"
    current_prompt_visible: bool = True


@dataclass(frozen=True)
class GenerationSemanticItem:
    content: str
    evidence: GenerationSourceEvidence


@dataclass(frozen=True)
class GenerationSemanticSection:
    kind: GenerationSectionKind
    items: tuple[GenerationSemanticItem, ...] = ()


@dataclass(frozen=True)
class GenerationPreparationBudget:
    """Upstream budget evidence; final prompt fitting remains PromptEngine-owned."""

    context_window: int
    entry_context_enabled: bool
    retrieval_invoked: bool
    retrieval_budget: int | None
    assembly_budget: int | None
    entry_block_tokens: int
    selected_entry_ids: tuple[str, ...]


@dataclass(frozen=True)
class ContinueGenerationInput:
    """Typed input whose sources were already owner- and chronology-checked."""

    target: GenerationTarget
    work: PreparedWorkContext
    characters: Sequence[PreparedCharacterContext]
    world: PreparedWorldContext | None
    lore: Sequence[PreparedLoreContext]
    prior_summaries: Sequence[PreparedPriorSummary]
    current_chapter: PreparedChapterContext
    instruction: str
    target_words: int
    context_window: int
    entry_blocks: Sequence[PreparedPromptBlock | PromptBlock] = ()
    entry_context_trace: FrozenMap | Mapping[str, object] = FrozenMap()


@dataclass(frozen=True)
class _NormalizedContinueGenerationInput:
    """Owned immutable values produced at the public preparation boundary."""

    target: GenerationTarget
    work: PreparedWorkContext
    characters: tuple[PreparedCharacterContext, ...]
    world: PreparedWorldContext | None
    lore: tuple[PreparedLoreContext, ...]
    prior_summaries: tuple[PreparedPriorSummary, ...]
    current_chapter: PreparedChapterContext
    instruction: str
    target_words: int
    context_window: int
    entry_blocks: tuple[PreparedPromptBlock, ...]
    entry_context_trace: FrozenMap


@dataclass(frozen=True)
class GenerationPreparation:
    """Canonical immutable context; sections/evidence are derived read-only views."""

    target: GenerationTarget
    work: PreparedWorkContext
    characters: tuple[PreparedCharacterContext, ...]
    world: PreparedWorldContext | None
    lore: tuple[PreparedLoreContext, ...]
    prior_summaries: tuple[PreparedPriorSummary, ...]
    current_chapter: PreparedChapterContext
    instruction: str
    constraints: tuple[GenerationConstraint, ...]
    budget: GenerationPreparationBudget
    entry_blocks: tuple[PreparedPromptBlock, ...]
    entry_context_trace: FrozenMap

    @property
    def sections(self) -> tuple[GenerationSemanticSection, ...]:
        return _build_semantic_sections(self)

    @property
    def evidence(self) -> tuple[GenerationSourceEvidence, ...]:
        selected = tuple(item.evidence for section in self.sections for item in section.items)
        return selected + _omitted_entry_evidence(self.entry_context_trace)

    def section(self, kind: GenerationSectionKind) -> GenerationSemanticSection:
        return self.sections[SECTION_ORDER.index(kind)]


def prepare_continue_generation(value: ContinueGenerationInput) -> GenerationPreparation:
    """Create one deterministic preparation without database/provider access."""

    normalized = _normalize_input(value)
    _validate_input(normalized)
    instruction = normalized.instruction or DEFAULT_CONTINUATION_INSTRUCTION
    constraints = (
        GenerationConstraint("target_words", normalized.target_words),
        GenerationConstraint("response_language", "ko"),
        GenerationConstraint("continuation_mode", normalized.target.operation.value),
    )
    return GenerationPreparation(
        target=normalized.target,
        work=normalized.work,
        characters=normalized.characters,
        world=normalized.world,
        lore=normalized.lore,
        prior_summaries=normalized.prior_summaries,
        current_chapter=normalized.current_chapter,
        instruction=instruction,
        constraints=constraints,
        budget=_build_budget(normalized.context_window, normalized.entry_context_trace),
        entry_blocks=normalized.entry_blocks,
        entry_context_trace=normalized.entry_context_trace,
    )


def _build_semantic_sections(
    value: GenerationPreparation,
) -> tuple[GenerationSemanticSection, ...]:
    """Derive the ordered semantic view from the canonical typed snapshot."""

    section_items: dict[GenerationSectionKind, list[GenerationSemanticItem]] = {
        kind: [] for kind in SECTION_ORDER
    }

    def add(
        section: GenerationSectionKind,
        *,
        content: str,
        source_type: str,
        source_id: str,
        source_order: int | None = None,
        current_prompt_visible: bool = True,
    ) -> None:
        order = len(section_items[section]) if source_order is None else source_order
        section_items[section].append(
            GenerationSemanticItem(
                content=content,
                evidence=GenerationSourceEvidence(
                    section=section,
                    source_type=source_type,
                    source_id=source_id,
                    selection_order=order,
                    current_prompt_visible=current_prompt_visible,
                ),
            )
        )

    add(
        GenerationSectionKind.STORY,
        content=_render_work(value.work),
        source_type="work",
        source_id=value.work.id,
        # Work metadata was not part of the legacy provider prompt.  It is now
        # explicit preparation material, while the compatibility formatter keeps
        # the current production payload unchanged in this PR.
        current_prompt_visible=False,
    )
    for character in value.characters:
        add(
            GenerationSectionKind.CHARACTERS,
            content=(
                f"- {character.name}: {character.personality} / "
                f"말투: {character.speech_style}"
            ),
            source_type="character",
            source_id=character.id,
        )
    if value.world is not None:
        add(
            GenerationSectionKind.CANON_CONTEXT,
            content=f"세계관: {value.world.name}\n{value.world.description}",
            source_type="world",
            source_id=value.world.id,
        )
    for lore in value.lore:
        add(
            GenerationSectionKind.CANON_CONTEXT,
            content=lore.content,
            source_type="lore_entry",
            source_id=lore.id,
        )

    for summary in value.prior_summaries:
        add(
            GenerationSectionKind.PRIOR_CHAPTER_SUMMARIES,
            content=summary.content,
            source_type="chapter.summary",
            source_id=summary.chapter_id,
            source_order=summary.chapter_index,
        )

    for block in value.entry_blocks:
        entry_type = str(block.metadata.get("entry_type", ""))
        source_id = str(block.metadata.get("entry_id", block.id.removeprefix("entry:")))
        if entry_type == "story.summary":
            chronology = block.metadata.get("story_summary_chronology")
            assert isinstance(chronology, FrozenMap)
            source_order = chronology.get("source_chapter_index")
            assert isinstance(source_order, int) and not isinstance(source_order, bool)
        else:
            source_order = None
        section = _section_for_entry_type(entry_type)
        add(
            section,
            content=block.content,
            source_type=f"entry:{entry_type}",
            source_id=source_id,
            source_order=source_order,
        )

    section_items[GenerationSectionKind.PRIOR_CHAPTER_SUMMARIES].sort(
        key=lambda item: (item.evidence.selection_order, item.evidence.source_type, item.evidence.source_id)
    )
    current_content = (
        f"[현재 챕터 끝부분]\n{value.current_chapter.tail}"
        if value.current_chapter.tail
        else ""
    )
    add(
        GenerationSectionKind.CURRENT_CHAPTER,
        content=current_content,
        source_type="chapter.tail",
        source_id=value.current_chapter.id,
    )
    add(
        GenerationSectionKind.INSTRUCTION,
        content=value.instruction,
        source_type="generation_request",
        source_id=value.target.chapter_id,
    )
    for constraint in value.constraints:
        add(
            GenerationSectionKind.CONSTRAINTS,
            content=f"{constraint.name}: {constraint.value}",
            source_type="generation_constraint",
            source_id=constraint.name,
            current_prompt_visible=constraint.name == "continuation_mode",
        )

    sections = tuple(
        GenerationSemanticSection(kind=kind, items=tuple(section_items[kind]))
        for kind in SECTION_ORDER
    )
    return sections


def _section_for_entry_type(entry_type: str) -> GenerationSectionKind:
    if entry_type == "story.summary":
        return GenerationSectionKind.PRIOR_CHAPTER_SUMMARIES
    if entry_type == "relationship.state":
        return GenerationSectionKind.RELATIONSHIPS
    if entry_type.startswith("character."):
        return GenerationSectionKind.CHARACTERS
    return GenerationSectionKind.CANON_CONTEXT


def _normalize_input(value: ContinueGenerationInput) -> _NormalizedContinueGenerationInput:
    """Detach the preparation from every caller-owned mutable container."""

    target = value.target
    work = value.work
    chapter = value.current_chapter
    world = value.world
    trace = _snapshot_frozen_map(value.entry_context_trace)
    return _NormalizedContinueGenerationInput(
        target=GenerationTarget(
            owner_id=target.owner_id,
            work_id=target.work_id,
            chapter_id=target.chapter_id,
            operation=target.operation,
        ),
        work=PreparedWorkContext(
            id=work.id,
            owner_id=work.owner_id,
            title=work.title,
            synopsis=work.synopsis,
            genre=work.genre,
            tags=tuple(_sequence_items(work.tags, "Work tags")),
        ),
        characters=tuple(
            PreparedCharacterContext(
                id=character.id,
                owner_id=character.owner_id,
                name=character.name,
                personality=character.personality,
                speech_style=character.speech_style,
            )
            for character in _sequence_items(value.characters, "Characters")
        ),
        world=(
            PreparedWorldContext(
                id=world.id,
                owner_id=world.owner_id,
                name=world.name,
                description=world.description,
                era=world.era,
            )
            if world is not None
            else None
        ),
        lore=tuple(
            PreparedLoreContext(
                id=lore.id,
                content=lore.content,
                keywords=tuple(_sequence_items(lore.keywords, "Lore keywords")),
                priority=lore.priority,
                scan_depth=lore.scan_depth,
                enabled=lore.enabled,
            )
            for lore in _sequence_items(value.lore, "Lore")
        ),
        prior_summaries=tuple(
            PreparedPriorSummary(
                chapter_id=summary.chapter_id,
                work_id=summary.work_id,
                chapter_index=summary.chapter_index,
                content=summary.content,
            )
            for summary in _sequence_items(value.prior_summaries, "Prior summaries")
        ),
        current_chapter=PreparedChapterContext(
            id=chapter.id,
            work_id=chapter.work_id,
            owner_id=chapter.owner_id,
            index=chapter.index,
            title=chapter.title,
            tail=chapter.tail,
        ),
        instruction=value.instruction,
        target_words=value.target_words,
        context_window=value.context_window,
        entry_blocks=tuple(
            _snapshot_entry_block(block)
            for block in _sequence_items(value.entry_blocks, "Entry blocks")
        ),
        entry_context_trace=trace,
    )


def _sequence_items(value: object, label: str) -> Sequence:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise TypeError(f"{label} must be a non-string sequence")
    return value


def _snapshot_frozen_map(value: FrozenMap | Mapping[str, object]) -> FrozenMap:
    if isinstance(value, FrozenMap):
        return freeze_mapping(thaw_mapping(value))
    if isinstance(value, Mapping):
        return freeze_mapping(value)
    raise TypeError("Entry context trace must be a mapping")


def _snapshot_entry_block(value: object) -> PreparedPromptBlock:
    if isinstance(value, PromptBlock):
        return PreparedPromptBlock.from_prompt_block(value)
    if isinstance(value, PreparedPromptBlock):
        return PreparedPromptBlock.from_prompt_block(value.to_prompt_block())
    raise TypeError("Entry blocks must be PromptBlock-compatible values")


def _validate_input(value: _NormalizedContinueGenerationInput) -> None:
    target = value.target
    if value.context_window < 1 or value.target_words < 1:
        raise ValueError("Generation budgets must be positive")
    if target.operation is not GenerationOperation.CONTINUE:
        raise ValueError("Only Chapter continuation preparation is supported")
    if value.work.id != target.work_id or value.work.owner_id != target.owner_id:
        raise ValueError("Generation target does not match Work authority")
    chapter = value.current_chapter
    if (
        chapter.id != target.chapter_id
        or chapter.work_id != target.work_id
        or chapter.owner_id != target.owner_id
    ):
        raise ValueError("Generation target does not match Chapter authority")
    if any(character.owner_id != target.owner_id for character in value.characters):
        raise ValueError("Foreign Character reached generation preparation")
    if value.world is not None and value.world.owner_id != target.owner_id:
        raise ValueError("Foreign World reached generation preparation")
    for summary in value.prior_summaries:
        if (
            not summary.chapter_id
            or summary.work_id != target.work_id
            or summary.chapter_id == target.chapter_id
            or isinstance(summary.chapter_index, bool)
            or not isinstance(summary.chapter_index, int)
            or summary.chapter_index < 1
            or summary.chapter_index >= chapter.index
        ):
            raise ValueError("Legacy prior summary evidence violates the target anchor")
    indexes = tuple(summary.chapter_index for summary in value.prior_summaries)
    if indexes != tuple(sorted(indexes)) or len(indexes) != len(set(indexes)):
        raise ValueError("Prior Chapter summaries are not in resolved story order")
    for block in value.entry_blocks:
        if block.metadata.get("entry_type") == "story.summary":
            _validate_entry_story_summary(block, target=target, target_index=chapter.index)


def _validate_entry_story_summary(
    block: PreparedPromptBlock, *, target: GenerationTarget, target_index: int
) -> None:
    """Assert upstream prior evidence without classifying or repairing it."""

    chronology = block.metadata.get("story_summary_chronology")
    source_id = chronology.get("source_chapter_id") if isinstance(chronology, FrozenMap) else None
    source_index = (
        chronology.get("source_chapter_index")
        if isinstance(chronology, FrozenMap)
        else None
    )
    if (
        block.metadata.get("scope_kind") != "work"
        or block.metadata.get("scope_id") != target.work_id
        or not isinstance(chronology, FrozenMap)
        or chronology.get("disposition") != "prior"
        or not isinstance(source_id, str)
        or not source_id
        or isinstance(source_index, bool)
        or not isinstance(source_index, int)
        or source_index < 1
        or source_id == target.chapter_id
        or source_index >= target_index
    ):
        raise ValueError("Entry story summary evidence is not a valid prior source")


def _render_work(work: PreparedWorkContext) -> str:
    lines = [f"제목: {work.title}"]
    if work.synopsis:
        lines.append(f"시놉시스: {work.synopsis}")
    if work.genre:
        lines.append(f"장르: {work.genre}")
    if work.tags:
        lines.append(f"태그: {', '.join(work.tags)}")
    return "\n".join(lines)


def _build_budget(context_window: int, trace: FrozenMap) -> GenerationPreparationBudget:
    def integer(name: str) -> int | None:
        value = trace.get(name)
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    selected = trace.get("selected_entry_ids", ())
    selected_ids = tuple(str(value) for value in selected) if isinstance(selected, tuple) else ()
    return GenerationPreparationBudget(
        context_window=context_window,
        entry_context_enabled=trace.get("feature_enabled") is True,
        retrieval_invoked=trace.get("retrieval_invoked") is True,
        retrieval_budget=integer("retrieval_budget"),
        assembly_budget=integer("assembly_budget"),
        entry_block_tokens=integer("entry_block_tokens") or 0,
        selected_entry_ids=selected_ids,
    )


def _omitted_entry_evidence(trace: FrozenMap) -> tuple[GenerationSourceEvidence, ...]:
    retrieval = trace.get("retrieval_exclusions")
    assembly = trace.get("assembly_exclusions")
    omitted: list[tuple[str, str, str]] = []
    if isinstance(retrieval, FrozenMap):
        type_map = retrieval.get("excluded_entry_types")

        def entry_type(entry_id: object) -> str:
            value = type_map.get(str(entry_id), "") if isinstance(type_map, FrozenMap) else ""
            return str(value)

        for key, reason in (
            ("orphaned_entry_ids", "orphaned_anchor"),
            ("retrieval_budget_rejected_entry_ids", "retrieval_budget_exceeded"),
            ("limit_rejected_entry_ids", "retrieval_limit_exceeded"),
        ):
            values = retrieval.get(key, ())
            if isinstance(values, tuple):
                omitted.extend(
                    (str(entry_id), reason, entry_type(entry_id)) for entry_id in values
                )
        chronology = retrieval.get("story_summary_chronology", ())
        if isinstance(chronology, tuple):
            for item in chronology:
                if isinstance(item, FrozenMap):
                    omitted.append(
                        (
                            str(item.get("entry_id", "")),
                            str(item.get("reason", "unknown")),
                            "story.summary",
                        )
                    )
    if isinstance(assembly, tuple):
        for item in assembly:
            if isinstance(item, FrozenMap):
                omitted.append(
                    (
                        str(item.get("entry_id", "")),
                        str(item.get("reason", "unknown")),
                        str(item.get("entry_type", "")),
                    )
                )
    return tuple(
        GenerationSourceEvidence(
            section=_section_for_entry_type(entry_type),
            source_type=f"entry:{entry_type}" if entry_type else "entry",
            source_id=entry_id,
            selection_order=index,
            selected=False,
            reason=reason,
            current_prompt_visible=False,
        )
        for index, (entry_id, reason, entry_type) in enumerate(omitted)
        if entry_id
    )


def snapshot_prompt_blocks(blocks: Sequence[PromptBlock]) -> tuple[PreparedPromptBlock, ...]:
    return tuple(PreparedPromptBlock.from_prompt_block(block) for block in blocks)
