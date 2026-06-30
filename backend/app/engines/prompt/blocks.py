"""PromptBlock definitions (design 9.5)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

BlockKind = Literal[
    "system", "persona", "character", "world", "lore",
    "memory", "history", "chapter", "user", "instruction",
]
BlockRole = Literal["system", "user", "assistant"]

# Layer ordering (design 9.8). Lower index renders earlier.
LAYER_ORDER: list[BlockKind] = [
    "system", "character", "persona", "world", "lore",
    "memory", "chapter", "history", "user", "instruction",
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
