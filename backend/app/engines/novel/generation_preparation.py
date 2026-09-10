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
    chapter_index: int
    content: str


@dataclass(frozen=True)
class PreparedPromptBlock:
    """Immutable snapshot of an existing provider-neutral PromptBlock."""

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
        return cls(
            id=block.id,
            role=block.role,
            kind=block.kind,
            content=block.content,
            priority=block.priority,
            token_count=block.token_count,
            truncatable=block.truncatable,
            metadata=freeze_mapping(block.metadata),
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
    characters: tuple[PreparedCharacterContext, ...]
    world: PreparedWorldContext | None
    lore: tuple[PreparedLoreContext, ...]
    prior_summaries: tuple[PreparedPriorSummary, ...]
    current_chapter: PreparedChapterContext
    instruction: str
    target_words: int
    context_window: int
    entry_blocks: tuple[PreparedPromptBlock, ...] = ()
    entry_context_trace: FrozenMap = FrozenMap()


@dataclass(frozen=True)
class GenerationPreparation:
    target: GenerationTarget
    work: PreparedWorkContext
    characters: tuple[PreparedCharacterContext, ...]
    world: PreparedWorldContext | None
    lore: tuple[PreparedLoreContext, ...]
    prior_summaries: tuple[PreparedPriorSummary, ...]
    current_chapter: PreparedChapterContext
    instruction: str
    constraints: tuple[GenerationConstraint, ...]
    sections: tuple[GenerationSemanticSection, ...]
    evidence: tuple[GenerationSourceEvidence, ...]
    budget: GenerationPreparationBudget
    entry_blocks: tuple[PreparedPromptBlock, ...]
    entry_context_trace: FrozenMap

    def __post_init__(self) -> None:
        if tuple(section.kind for section in self.sections) != SECTION_ORDER:
            raise ValueError("Generation semantic section order is not canonical")


def prepare_continue_generation(value: ContinueGenerationInput) -> GenerationPreparation:
    """Create one deterministic preparation without database/provider access."""

    _validate_input(value)
    instruction = value.instruction or DEFAULT_CONTINUATION_INSTRUCTION
    constraints = (
        GenerationConstraint("target_words", value.target_words),
        GenerationConstraint("response_language", "ko"),
        GenerationConstraint("continuation_mode", value.target.operation.value),
    )
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
            if not isinstance(chronology, FrozenMap):
                raise ValueError("Entry story summary chronology evidence is missing")
            source_order = chronology.get("source_chapter_index")
            if isinstance(source_order, bool) or not isinstance(source_order, int):
                raise ValueError("Entry story summary source position is missing")
            section = GenerationSectionKind.PRIOR_CHAPTER_SUMMARIES
        elif entry_type == "relationship.state":
            source_order = None
            section = GenerationSectionKind.RELATIONSHIPS
        elif entry_type.startswith("character."):
            source_order = None
            section = GenerationSectionKind.CHARACTERS
        else:
            source_order = None
            section = GenerationSectionKind.CANON_CONTEXT
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
        content=instruction,
        source_type="generation_request",
        source_id=value.target.chapter_id,
    )
    for constraint in constraints:
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
    selected_evidence = tuple(item.evidence for section in sections for item in section.items)
    omitted_evidence = _omitted_entry_evidence(value.entry_context_trace)
    budget = _build_budget(value.context_window, value.entry_context_trace)
    return GenerationPreparation(
        target=value.target,
        work=value.work,
        characters=value.characters,
        world=value.world,
        lore=value.lore,
        prior_summaries=value.prior_summaries,
        current_chapter=value.current_chapter,
        instruction=instruction,
        constraints=constraints,
        sections=sections,
        evidence=selected_evidence + omitted_evidence,
        budget=budget,
        entry_blocks=value.entry_blocks,
        entry_context_trace=value.entry_context_trace,
    )


def _validate_input(value: ContinueGenerationInput) -> None:
    target = value.target
    if value.context_window < 1 or value.target_words < 1:
        raise ValueError("Generation budgets must be positive")
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
    indexes = tuple(summary.chapter_index for summary in value.prior_summaries)
    if indexes != tuple(sorted(indexes)) or len(indexes) != len(set(indexes)):
        raise ValueError("Prior Chapter summaries are not in resolved story order")


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
    omitted: list[tuple[str, str]] = []
    if isinstance(retrieval, FrozenMap):
        for key, reason in (
            ("orphaned_entry_ids", "orphaned_anchor"),
            ("retrieval_budget_rejected_entry_ids", "retrieval_budget_exceeded"),
            ("limit_rejected_entry_ids", "retrieval_limit_exceeded"),
        ):
            values = retrieval.get(key, ())
            if isinstance(values, tuple):
                omitted.extend((str(entry_id), reason) for entry_id in values)
        chronology = retrieval.get("story_summary_chronology", ())
        if isinstance(chronology, tuple):
            for item in chronology:
                if isinstance(item, FrozenMap):
                    omitted.append((str(item.get("entry_id", "")), str(item.get("reason", "unknown"))))
    if isinstance(assembly, tuple):
        for item in assembly:
            if isinstance(item, FrozenMap):
                omitted.append((str(item.get("entry_id", "")), str(item.get("reason", "unknown"))))
    return tuple(
        GenerationSourceEvidence(
            section=GenerationSectionKind.CANON_CONTEXT,
            source_type="entry",
            source_id=entry_id,
            selection_order=index,
            selected=False,
            reason=reason,
            current_prompt_visible=False,
        )
        for index, (entry_id, reason) in enumerate(omitted)
        if entry_id
    )


def snapshot_prompt_blocks(blocks: Sequence[PromptBlock]) -> tuple[PreparedPromptBlock, ...]:
    return tuple(PreparedPromptBlock.from_prompt_block(block) for block in blocks)
