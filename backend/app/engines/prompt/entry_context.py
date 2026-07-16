"""Pure Entry retrieval result to PromptBlock context assembly bridge.

Retrieval owns database access, eligibility, ranking, and content-level budget
selection. This module accepts only an already-selected retrieval result. It
renders prompt-ready blocks, re-estimates the rendered text, and applies an
assembly budget without truncating an Entry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.engines.prompt.blocks import DEFAULT_PRIORITY, PromptBlock
from app.engines.prompt.tokenizer import Tokenizer, default_tokenizer
from app.schemas.entry import EntryRetrievalItem, EntryRetrievalResult, EntryRetrievalTrace

ENTRY_STORE_SOURCE = "entry_store"
ASSEMBLY_POLICY_VERSION = "entry-prompt-block-v1"
ASSEMBLY_BUDGET_EXCLUSION: Literal[
    "rendered_block_budget_exceeded"
] = "rendered_block_budget_exceeded"


@dataclass(frozen=True)
class EntryContextAssemblyRequest:
    """Selected retrieval output plus a required rendered-block budget."""

    retrieval_result: EntryRetrievalResult
    budget: int

    def __post_init__(self) -> None:
        if isinstance(self.budget, bool) or not isinstance(self.budget, int) or self.budget < 1:
            raise ValueError("budget must be a positive integer")


@dataclass(frozen=True)
class EntryContextAssemblyExclusion:
    entry_id: str
    reason: Literal["rendered_block_budget_exceeded"]
    rendered_tokens: int
    budget_remaining: int
    stage: Literal["context_assembly"] = "context_assembly"


@dataclass(frozen=True)
class EntryContextAssemblyTrace:
    """Keeps retrieval exclusions distinct from rendered-block exclusions."""

    retrieval: EntryRetrievalTrace
    assembly_exclusions: list[EntryContextAssemblyExclusion] = field(default_factory=list)


@dataclass(frozen=True)
class EntryContextAssemblyResult:
    blocks: list[PromptBlock]
    included_entry_ids: list[str]
    assembly_excluded_entry_ids: list[str]
    budget_used: int
    requested_budget: int
    source_retrieval_policy_version: str
    assembly_policy_version: str
    trace: EntryContextAssemblyTrace


def render_entry_prompt_text(item: EntryRetrievalItem) -> str:
    """Render deterministic, compact prompt text for one selected Entry."""

    entry = item.entry
    heading = f"[{entry.type.value}]"
    title = (entry.title or "").strip()
    if title:
        heading = f"{heading} {title}"
    return f"{heading}\n{entry.content.strip()}"


def entry_retrieval_item_to_prompt_block(
    item: EntryRetrievalItem,
    *,
    policy_version: str,
    tokenizer: Tokenizer = default_tokenizer,
) -> PromptBlock:
    """Convert one selected item without filtering, ranking, or persistence."""

    entry = item.entry
    content = render_entry_prompt_text(item)
    metadata: dict[str, object] = {
        "source": ENTRY_STORE_SOURCE,
        "policy_version": policy_version,
        "assembly_policy_version": ASSEMBLY_POLICY_VERSION,
        "entry_id": entry.id,
        "entry_type": entry.type.value,
        "entry_status": entry.status.value,
        "scope_kind": entry.scope_kind.value,
        "scope_id": entry.scope_id,
        "subject_type": entry.subject_type.value if entry.subject_type is not None else None,
        "subject_id": entry.subject_id,
        "title": entry.title,
        "label": entry.title or entry.type.value,
        "retrieval_score": item.score,
        "retrieval_reason": list(item.reason),
        "matched_terms": list(item.matched_terms),
        "score_breakdown": item.score_breakdown.model_dump(),
        "provenance": dict(entry.provenance),
        "confidence": entry.confidence,
        "priority": entry.priority,
        "retrieval_estimated_tokens": item.estimated_tokens,
    }
    token_count = tokenizer.count(content)
    metadata["rendered_estimated_tokens"] = token_count
    return PromptBlock(
        id=f"entry:{entry.id}",
        role="system",
        kind="memory",
        content=content,
        priority=DEFAULT_PRIORITY["memory"],
        token_count=token_count,
        truncatable=False,
        metadata=metadata,
    )


def assemble_entry_context(
    request: EntryContextAssemblyRequest,
    *,
    tokenizer: Tokenizer = default_tokenizer,
) -> EntryContextAssemblyResult:
    """Fit rendered Entry blocks in retrieval order, excluding only whole blocks."""

    retrieval = request.retrieval_result
    blocks: list[PromptBlock] = []
    included_entry_ids: list[str] = []
    exclusions: list[EntryContextAssemblyExclusion] = []
    used = 0

    for item in retrieval.items:
        block = entry_retrieval_item_to_prompt_block(
            item,
            policy_version=retrieval.policy_version,
            tokenizer=tokenizer,
        )
        remaining = request.budget - used
        if block.token_count > remaining:
            exclusions.append(
                EntryContextAssemblyExclusion(
                    entry_id=item.entry.id,
                    reason=ASSEMBLY_BUDGET_EXCLUSION,
                    rendered_tokens=block.token_count,
                    budget_remaining=remaining,
                )
            )
            continue
        blocks.append(block)
        included_entry_ids.append(item.entry.id)
        used += block.token_count

    return EntryContextAssemblyResult(
        blocks=blocks,
        included_entry_ids=included_entry_ids,
        assembly_excluded_entry_ids=[exclusion.entry_id for exclusion in exclusions],
        budget_used=used,
        requested_budget=request.budget,
        source_retrieval_policy_version=retrieval.policy_version,
        assembly_policy_version=ASSEMBLY_POLICY_VERSION,
        trace=EntryContextAssemblyTrace(
            retrieval=retrieval.trace.model_copy(deep=True),
            assembly_exclusions=exclusions,
        ),
    )
