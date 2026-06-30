"""PromptEngine — assembly pipeline (design 9.6).

collect -> resolve variables -> inject/order -> budget/truncate -> finalize.
Output is a provider-neutral AssembledPrompt (design 9.13). Lore scanning runs
inside the engine against `history` (design 9.11.2). Guarantees Property 7.
"""
from __future__ import annotations

import re
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
from app.engines.prompt.budget import BudgetManager
from app.engines.prompt.tokenizer import Tokenizer, default_tokenizer

_VAR_RE = re.compile(r"\{\{([\w\.]+)\}\}")


@dataclass
class AssembleInput:
    template_body: str
    character: object | None = None
    persona: object | None = None
    world: object | None = None
    lore_entries: list = None  # list[LoreEntry-like]
    memory_short: list = None  # list[Message-like]
    memory_long: list = None  # list[Memory-like]
    history: list = None  # list[Message-like]
    chapter_prior_summaries: list[str] = None
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

        def add(kind: BlockKind, role, content: str, *, priority=None, truncatable=True, bid=None):
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
                )
            )

        add("system", "system", inp.template_body, truncatable=False)
        if inp.character is not None:
            c = inp.character
            parts = [
                f"이름: {getattr(c, 'name', '')}",
                f"성격: {getattr(c, 'personality', '')}",
                f"말투: {getattr(c, 'speech_style', '')}",
            ]
            add("character", "system", "\n".join(p for p in parts if p.split(": ", 1)[1]))
        if inp.persona is not None:
            add(
                "persona",
                "system",
                f"사용자 페르소나: {getattr(inp.persona, 'name', '')} — {getattr(inp.persona, 'description', '')}",
            )
        if inp.world is not None:
            w = inp.world
            add("world", "system", f"세계관: {getattr(w, 'name', '')}\n{getattr(w, 'description', '')}")
        blocks.extend(self._make_lore_blocks(inp))
        for mem in inp.memory_long or []:
            add("memory", "system", getattr(mem, "content", ""), priority=60)
        for s in inp.chapter_prior_summaries or []:
            add("chapter", "system", s, priority=DEFAULT_PRIORITY["chapter"])
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
        return sorted(
            blocks,
            key=lambda b: (order_index.get(b.kind, 99), -b.priority),
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
            b.content = self._resolve(b.content, ctx)
            b.token_count = self.tok.count(b.content)
        ordered = self._order(blocks)
        budget = self.budget.compute_budget(inp.context_window, inp.max_tokens, inp.safety_ratio)
        result = self.budget.fit(ordered, budget)

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
