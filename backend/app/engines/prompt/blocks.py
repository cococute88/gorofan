"""PromptBlock definitions (design 9.5)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

BlockKind = Literal[
    "system", "persona", "character", "world", "lore",
    "entry", "memory", "history", "chapter", "user", "instruction",
]
BlockRole = Literal["system", "user", "assistant"]

# Layer ordering (design 9.8). Lower index renders earlier.
# `entry` sits with the other knowledge layers, between legacy `lore` and
# chat-private `memory`. Inserting it there leaves every pre-existing kind in
# its original relative position, so a prompt without Entry blocks renders
# exactly as before (P1-6).
LAYER_ORDER: list[BlockKind] = [
    "system", "character", "persona", "world", "lore",
    "entry", "memory", "chapter", "history", "user", "instruction",
]

# Default priorities (design 9.6). Higher = kept longer (dropped/trimmed last).
DEFAULT_PRIORITY: dict[BlockKind, int] = {
    "system": 100,
    "user": 1000,
    "instruction": 1000,
    "character": 90,
    "persona": 80,
    "world": 70,
    "chapter": 75,
    # Entry Store canon is human-gated shared knowledge (ADR-003/RFC-002), so it
    # outranks chat-private `memory` and the legacy keyword `lore` scan. It stays
    # below the structural identity/continuity blocks because P1-6 is additive:
    # legacy Character/World/Lore/chapter context remains authoritative until the
    # separately approved P1-8 cutover. Total Entry volume is bounded by the
    # retrieval knowledge-slice budget (RFC-003 §11.1), not by this priority, so
    # Entry cannot unboundedly displace `memory`.
    "entry": 65,
    "memory": 60,
    "history": 30,
    "lore": 50,
}


@dataclass
class PromptBlock:
    id: str
    role: BlockRole
    kind: BlockKind
    content: str
    priority: int
    token_count: int = 0
    truncatable: bool = True
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class TraceEntry:
    block_id: str
    kind: BlockKind
    priority: int
    token_count: int
    status: Literal["included", "dropped", "trimmed"]
    trimmed_tokens: int = 0


@dataclass
class BudgetResult:
    included: list[PromptBlock] = field(default_factory=list)
    dropped: list[PromptBlock] = field(default_factory=list)
    trimmed: list[tuple[PromptBlock, int]] = field(default_factory=list)
    final_tokens: int = 0
    budget: int = 0
