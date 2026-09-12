"""PromptEngine — assembly pipeline (design 9.6).

collect -> resolve variables -> inject/order -> budget/truncate -> finalize.
Output is a provider-neutral AssembledPrompt (design 9.13). Lore scanning runs
inside the engine against `history` (design 9.11.2). Guarantees Property 7.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.adapters.base import AssembledPrompt, ChatMessage
from app.core.errors import ValidationAppError
from app.engines.prompt.blocks import (
    DEFAULT_PRIORITY,
    LAYER_ORDER,
    BlockKind,
    PromptBlock,
    TraceEntry,
)
from app.engines.prompt.budget import BudgetManager, PromptBudgetError
from app.engines.prompt.tokenizer import Tokenizer, default_tokenizer

_VAR_RE = re.compile(r"\{\{([\w\.]+)\}\}")


@dataclass(frozen=True)
class RenderedFieldBlock:
    """Provider text plus source-identity spans for aggregate legacy fields."""

    content: str
    field_spans: dict[str, tuple[int, int]]


def render_character_block(
    character: object, *, transform: Callable[[str], str] | None = None
) -> RenderedFieldBlock:
    """Render the production Character block and retain each field's exact span."""

    apply = transform or (lambda value: value)
    pieces: list[str] = []
    spans: dict[str, tuple[int, int]] = {}
    for field_name, label in (
        ("name", "이름: "),
        ("personality", "성격: "),
        ("speech_style", "말투: "),
    ):
        raw_value = str(getattr(character, field_name, ""))
        if not raw_value:
            continue
        if pieces:
            pieces.append("\n")
        pieces.append(label)
        value = apply(raw_value)
        start = sum(len(piece) for piece in pieces)
        pieces.append(value)
        spans[field_name] = (start, start + len(value))
    return RenderedFieldBlock(content="".join(pieces), field_spans=spans)


def render_world_block(
    world: object, *, transform: Callable[[str], str] | None = None
) -> RenderedFieldBlock:
    """Render the production World block and retain name/description spans."""

    apply = transform or (lambda value: value)
    name = apply(str(getattr(world, "name", "")))
    description = apply(str(getattr(world, "description", "")))
    prefix = "세계관: "
    content = f"{prefix}{name}\n{description}"
    description_start = len(prefix) + len(name) + 1
    return RenderedFieldBlock(
        content=content,
        field_spans={
            "name": (len(prefix), len(prefix) + len(name)),
            "description": (description_start, description_start + len(description)),
        },
    )


@dataclass
class AssembleInput:
    template_body: str
    prompt_asset_id: str | None = None
    prompt_asset_version: str | None = None
    prompt_asset_sha256: str | None = None
    character: object | None = None
    persona: object | None = None
    world: object | None = None
    lore_entries: list | None = None  # list[LoreEntry-like]
    memory_short: list | None = None  # list[Message-like]
    memory_long: list | None = None  # list[Memory-like]
    history: list | None = None  # list[Message-like]
    chapter_prior_summaries: list[str] | None = None
    chapter_prior_summary_indexes: list[int] | None = None
    # Already-assembled Entry Store blocks (P1-6). The caller owns retrieval and
    # Context Assembly; the engine only collects, orders, and budgets them.
    entry_blocks: list[PromptBlock] | None = None
    entry_context_trace: dict[str, object] | None = None
    user_message: str | None = None
    instruction: str | None = None
    user_display_name: str = "창작자"
    # budget params
    context_window: int = 8192
    max_tokens: int = 1024
    safety_ratio: float = 0.08


class PromptEngine:
    def __init__(self, tokenizer: Tokenizer | None = None) -> None:
        self.tok = tokenizer or default_tokenizer
        self.budget = BudgetManager(self.tok)

    # ----- variable resolution (design 9.10) -----
    def _ctx(self, inp: AssembleInput) -> dict[str, str]:
        ctx: dict[str, str] = {"user": inp.user_display_name}
        c = inp.character
        if c is not None:
            ctx["char"] = getattr(c, "name", "")
            ctx["char.personality"] = getattr(c, "personality", "")
            ctx["char.speech_style"] = getattr(c, "speech_style", "")
        if inp.persona is not None:
            ctx["persona"] = getattr(inp.persona, "name", "")
            ctx["persona.description"] = getattr(inp.persona, "description", "")
        w = inp.world
        if w is not None:
            ctx["world"] = getattr(w, "name", "")
            ctx["world.description"] = getattr(w, "description", "")
            ctx["world.era"] = getattr(w, "era", "")
        return ctx

    def _resolve(self, content: str, ctx: dict[str, str]) -> str:
        return _VAR_RE.sub(lambda m: ctx.get(m.group(1), ""), content)

    # ----- lore scan (design 9.11.2) -----
    def _make_lore_blocks(self, inp: AssembleInput) -> list[PromptBlock]:
        entries = inp.lore_entries or []
        history = inp.history or []
        depth = max((getattr(e, "scan_depth", 4) for e in entries), default=4)
        recent = history[-depth:] if history else []
        text = " ".join(getattr(m, "content", "") for m in recent)
        if inp.user_message:
            text += " " + inp.user_message
        if inp.instruction:
            text += " " + inp.instruction
        matched: list[PromptBlock] = []
        for e in entries:
            if not getattr(e, "enabled", True):
                continue
            keywords = getattr(e, "keywords", []) or []
            if any(kw and kw in text for kw in keywords):
                matched.append(
                    PromptBlock(
                        id=f"lore:{getattr(e, 'id', len(matched))}",
                        role="system",
                        kind="lore",
                        content=getattr(e, "content", ""),
                        priority=getattr(e, "priority", DEFAULT_PRIORITY["lore"]),
                    )
                )
        return matched

    # ----- collect (design 9.6) -----
    def _collect(self, inp: AssembleInput) -> list[PromptBlock]:
        blocks: list[PromptBlock] = []

        def add(
            kind: BlockKind,
            role,
            content: str,
            *,
            priority=None,
            truncatable=True,
            bid=None,
            metadata: dict[str, object] | None = None,
        ):
            if not content:
                return
            blocks.append(
                PromptBlock(
                    id=bid or f"{kind}:{len(blocks)}",
                    role=role,
                    kind=kind,
                    content=content,
                    priority=priority if priority is not None else DEFAULT_PRIORITY[kind],
                    truncatable=truncatable,
                    metadata=dict(metadata or {}),
                )
            )

        add("system", "system", inp.template_body, truncatable=False)
        if inp.character is not None:
            add("character", "system", render_character_block(inp.character).content)
        if inp.persona is not None:
            add(
                "persona",
                "system",
                f"사용자 페르소나: {getattr(inp.persona, 'name', '')} — {getattr(inp.persona, 'description', '')}",
            )
        if inp.world is not None:
            add("world", "system", render_world_block(inp.world).content)
        blocks.extend(self._make_lore_blocks(inp))
        # Entry Store canon joins as its own kind, alongside — never merged into —
        # the legacy lore blocks above and the chat-private memory blocks below.
        blocks.extend(inp.entry_blocks or [])
        for mem in inp.memory_long or []:
            add("memory", "system", getattr(mem, "content", ""), priority=60)
        prior_summary_indexes = inp.chapter_prior_summary_indexes or []
        for position, summary in enumerate(inp.chapter_prior_summaries or []):
            metadata: dict[str, object] = {}
            if position < len(prior_summary_indexes):
                metadata = {
                    "prepared_render_group": "story_summary",
                    "prepared_render_order": prior_summary_indexes[position],
                }
            add(
                "chapter",
                "system",
                summary,
                priority=DEFAULT_PRIORITY["chapter"],
                metadata=metadata,
            )
        # short-term/history as conversation turns
        history_src = (inp.memory_short or []) + (inp.history or [])
        seen_ids = set()
        for i, m in enumerate(history_src):
            mid = getattr(m, "id", None)
            if mid is not None and mid in seen_ids:
                continue
            if mid is not None:
                seen_ids.add(mid)
            role = getattr(m, "role", "user")
            if role == "system":
                continue
            add("history", role, getattr(m, "content", ""), priority=DEFAULT_PRIORITY["history"] + i)
        if inp.user_message:
            add("user", "user", inp.user_message, truncatable=True)
        if inp.instruction:
            add("instruction", "user", f"[집필 지시] {inp.instruction}", truncatable=True)
        return blocks

    def _order(self, blocks: list[PromptBlock]) -> list[PromptBlock]:
        order_index = {k: i for i, k in enumerate(LAYER_ORDER)}

        def key(block: PromptBlock) -> tuple[int, int, int]:
            if block.metadata.get("prepared_render_group") == "story_summary":
                render_order = block.metadata.get("prepared_render_order")
                if isinstance(render_order, int) and not isinstance(render_order, bool):
                    return (order_index["chapter"], render_order, 0)
            return (order_index.get(block.kind, 99), 0, -block.priority)

        return sorted(
            blocks,
            key=key,
        )

    # ----- assemble (design 9.6) -----
    def assemble(self, inp: AssembleInput) -> AssembledPrompt:
        if inp.context_window < inp.max_tokens:
            raise ValidationAppError(
                "context_window must be >= max_tokens", {"inv": "INV-6"}
            )
        ctx = self._ctx(inp)
        blocks = self._collect(inp)
        for b in blocks:
            # Entry content is stored canon, not an authored template. Running
            # variable substitution over it would let `{{...}}` inside a user's
            # own knowledge silently rewrite the fact being injected, so Entry
            # blocks are collected verbatim. Tokens are still recounted here
            # because the engine owns the final budget (RFC-003 §12).
            if b.kind != "entry":
                b.content = self._resolve(b.content, ctx)
            b.token_count = self.tok.count(b.content)
        ordered = self._order(blocks)
        budget: int | None = None
        try:
            budget = self.budget.compute_budget(
                inp.context_window, inp.max_tokens, inp.safety_ratio
            )
            result = self.budget.fit(ordered, budget)
        except PromptBudgetError as exc:
            details: dict[str, object] = {"inv": "INV-7"}
            if budget is not None:
                details["budget"] = budget
            raise ValidationAppError(
                "Prompt cannot fit the available context budget",
                details,
            ) from exc

        # finalize to neutral messages, preserving order
        final_order = {id(b): i for i, b in enumerate(ordered)}
        included = sorted(result.included, key=lambda b: final_order.get(id(b), 0))
        messages: list[ChatMessage] = []
        system_text_parts: list[str] = []
        for b in included:
            if b.role == "system":
                system_text_parts.append(b.content)
            messages.append(ChatMessage(role=b.role, content=b.content))
        token_count = result.final_tokens

        trace = {
            "budget": result.budget,
            "final_tokens": token_count,
            "context_window": inp.context_window,
            "max_tokens": inp.max_tokens,
            "entries": [
                _trace_entry(b, "included").__dict__ for b in result.included
            ]
            + [_trace_entry(b, "dropped").__dict__ for b in result.dropped],
        }
        if inp.prompt_asset_id is not None:
            trace["prompt_asset"] = {
                "id": inp.prompt_asset_id,
                "version": inp.prompt_asset_version,
                "sha256": inp.prompt_asset_sha256,
            }
        if inp.entry_context_trace is not None:
            trace["entry_context"] = inp.entry_context_trace
        # Property 7 defensive assertion
        assert token_count <= inp.context_window, "Property 7 violated"
        return AssembledPrompt(
            messages=messages,
            token_count=token_count,
            system="\n\n".join(p for p in system_text_parts if p) or None,
            trace=trace,
        )


def _trace_entry(b: PromptBlock, status) -> TraceEntry:  # noqa: ANN001
    return TraceEntry(
        block_id=b.id, kind=b.kind, priority=b.priority,
        token_count=b.token_count, status=status,
    )
