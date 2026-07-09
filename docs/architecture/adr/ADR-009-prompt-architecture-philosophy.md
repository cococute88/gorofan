# ADR-009: Prompt Architecture Philosophy

- **Status:** Accepted (revised v2 — **validated as substrate**; assembly now feeds from the Entry store and is driven by declarative stages)
- **Date:** 2026-07-09 (v1) · revised 2026-07-09 (v2)
- **Deciders:** Architecture Review Board
- **Related:** ADR-002, ADR-004, ADR-005, ADR-013, ADR-016, ADR-018

> **v2 note.** Both Fable reviews explicitly place the block/budget PromptEngine in the **substrate to keep as-is** (`architecture-final-minimal.md` §1: *"PromptEngine (blocks/budget)"*). This ADR is therefore validated. Two alignments only: (1) the Engine's context sources are now **Store entries** returned by the single `retrieve()` function (ADR-018), not scattered per-type reads; (2) *which* blocks to assemble for a given step is chosen by the **declarative Writer stage** (ADR-005), while the Engine remains the deterministic, budgeted, provider-neutral assembler. The "no feature hand-assembles prompts" rule is unchanged and reinforced by stages-as-data.

## 1. Context

Prompt assembly is the product's genuine technical crown jewel (`design.md` §9). Every generation — chat or novel — depends on turning scattered context (system template, persona, character, world, lore, memory, history, chapter context, user input) into a single, budget-fitting, provider-neutral message list. Do this badly and quality collapses regardless of model.

The existing design already specifies a strong approach: **priority-ordered `PromptBlock`s → variable resolution → injection/ordering → token-budget truncation → neutral `messages[]`**, with protected blocks (user message, system) that are never dropped, keyword-triggered lore scanning, a prompt cache, and a debug trace. The Board's job is to ratify this as the philosophy and lock its invariants, not to redesign it.

The main risk in AI-native prompt systems is **ad-hoc string concatenation** scattered across features — unbudgeted, untestable, provider-coupled, and impossible to reason about when output degrades.

## 2. Decision

**Adopt the block-based, budget-aware, provider-neutral Prompt Engine as the single, mandatory path for all prompt construction. No feature may hand-assemble prompt strings outside it.**

Locked principles (the "prompt constitution"):
1. **Everything is a `PromptBlock`** with an explicit `kind`, target `role`, `priority`, token count, and `truncatable` flag. Context is *collected as blocks*, never concatenated ad hoc.
2. **Deterministic pipeline:** collect → resolve variables → order → budget/fit → finalize. Each stage is close to a pure function (testable, reproducible given inputs).
3. **Token budget is an invariant, not a hope.** `context_window ≥ max_tokens` is a precondition (Property 6); assembled tokens ≤ `context_window` is guaranteed by priority-based truncation/drop (Property 7). The user message and system blocks are **never** truncated away (`design.md` §9.9).
4. **Provider-neutral output.** The Engine emits a neutral `messages[]`; provider-specific rendering (how system messages are handled, etc.) is the Adapter's job (ADR-016). The Engine never encodes provider quirks.
5. **Safe variable resolution:** unresolved placeholders resolve to blank, never to a crash or a leaked `{{token}}` (`design.md` §9.10).
6. **The Bible is the Engine's read source** (ADR-004): lore is keyword-scanned over recent context and injected by priority; memory is ranked and injected within budget.
7. **Observability is built in:** a debug/trace view accounts for included/dropped/trimmed blocks and token math (dev-only, L3), so quality regressions are diagnosable.
8. **Caching by content hash** (block hash + memory version) avoids recomputing identical assemblies (`design.md` §9.11.3) — an optimization, never a correctness dependency.

## 3. Alternatives Considered

- **A. Ad-hoc string templates per feature** — each engine builds its own prompt string with f-strings/format.
- **B. Third-party prompt/orchestration framework** (LangChain-style templating/chains) as the assembly layer.
- **C. Model-specific prompt builders** — a separate assembler per provider to exploit each model's ideal format.
- **D. Unbudgeted "just send everything"** — rely on large context windows and let the provider truncate.

## 4. Why Rejected

- **A — Ad-hoc per feature:** No shared budgeting, no truncation guarantees, no testability, guaranteed drift between chat and novel, and impossible to reason about when output degrades. This is exactly the failure mode the Engine exists to prevent. Rejected outright.
- **B — Framework:** Couples the core differentiator to a fast-moving external abstraction (a lock-in the product explicitly avoids), obscures the deterministic control we need for budget guarantees and tests, and adds dependency weight. We keep prompt assembly as first-party, plain, inspectable code. Rejected.
- **C — Per-provider builders:** Multiplies the most important code path by the number of providers, guaranteeing inconsistency and maintenance pain. The right seam is: neutral assembly in the Engine, thin provider rendering in the Adapter (ADR-016). Rejected.
- **D — Send everything, let provider truncate:** Non-deterministic, wastes tokens/cost, silently drops *whatever the provider chooses* (often the wrong thing — e.g. the system instructions or the user's message), and breaks on small-context/local models (Ollama). Directly violates Property 7. Rejected.

## 5. Consequences

**Positive**
- One tested, deterministic assembly path for the whole product → consistent behavior, diagnosable regressions.
- Hard budget guarantees make the product robust across wildly different context windows (giant cloud models to small local ones).
- Provider neutrality is preserved at the most important layer, reinforcing No-Vendor-Lock-in (ADR-016).
- The block/priority model is the natural insertion point for every future context source (reference style Entries, relationship Entries) without new machinery.

**Negative**
- Accurate token counting across providers is genuinely hard (esp. CJK/Korean and providers without an exposed tokenizer); the Engine must use approximate counts + a safety margin (AC-PROMPT-6), which can waste a little budget.
- Priority tuning (what drops first) is a subtle, ongoing craft; wrong priorities silently hurt quality.
- The block abstraction is more upfront code than string concatenation (justified by everything above).

**Future risks**
- New context sources could be injected *outside* the Engine "just this once" — the rule "no feature hand-assembles prompts" must be enforced (code review / a lint or test).
- Tokenizer drift as providers change models; the tokenizer abstraction must stay swappable.

## 6. Future Revisit Conditions

- If token-count inaccuracy causes frequent over/under-budget behavior, revisit tokenizer strategy (per-provider tokenizers, better approximations) — without abandoning the neutral-assembly principle.
- If a compelling provider feature (structured/tool messages, prompt-caching APIs) can't be expressed as neutral blocks, revisit the neutral-`messages[]` contract at the Engine↔Adapter seam, keeping provider quirks in the Adapter.
- If priority tuning becomes a recurring quality lever, consider surfacing it in the Bench (ADR-012) to make tuning measurable rather than intuitive.
