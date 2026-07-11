# RFC-009: Prompt System

- **Status:** Draft
- **Date:** 2026-07-10
- **Author:** Chief Software Architect
- **Project:** AI Native Creative Workspace (`ai-creative-workspace` / "gorofan") — "나만의 로판AI + 하트픽션"
- **Conforms to:** RFC-001, RFC-002, RFC-008, RFC-004, RFC-005, RFC-006, RFC-007, RFC-003; ADR-013, ADR-009, ADR-016, ADR-005, ADR-008, ADR-012, ADR-001
- **Supersedes:** nothing
- **RFC layer:** Component — the prompt-composition-and-versioning reference the Writer, Analyst, Bench, and provider-adapter RFCs build on

> **Reading order.** RFC-001 is the system-level reference; RFC-002 the Entry Store; RFC-008 the Analyst; RFC-004 the Writer; RFC-005 the Story Bible; RFC-006 the Relationship model; RFC-007 Character DNA; RFC-003 Store-wide Retrieval. Read them first. This RFC defines the **Prompt System** — the layer responsible for turning *assembled context* into a *provider-ready prompt*, and for defining how prompts are **composed, versioned, and evolved** over time. It explains *why it exists* and *what it owns and does not own*. It does **not** define prompt contents, templates, wording, block structures, models, or provider APIs — each is named and deferred.
>
> **Source of truth.** The RFC documents take precedence over this one, in order (RFC-001, then RFC-002…RFC-003); behind them the ADR set (`docs/architecture/adr/`) is authoritative, and the two reviews (`docs/design-review-ai-author-os.md`, `docs/architecture-final-minimal.md`) supply rationale only. Where anything here appears to conflict with an RFC or an ADR, **those win** and this document is in error.
>
> **Relationship to RFC-003.** RFC-003 defines Store-wide Entry selection and the traceable Entry-to-PromptBlock handoff. This RFC and ADR-009 define prompt bodies and the deterministic, budgeted, provider-neutral assembly discipline. Retrieval selects knowledge; prompt assembly composes it with all other inputs.
>
> **This RFC is implementation-neutral.** Whenever an implementation detail is needed, it writes **"Defined in the corresponding RFC"** (naming the topic) and stops. It defines no prompt blocks and no templates.

---

## 1. Purpose

Every generation the product performs is, at the last step, a **prompt** — and the quality of that prompt is the quality ceiling of the output. Retrieved Entries (RFC-003) are part of the material; a prompt is what that material becomes when combined with the authored, versioned instruction and non-Store inputs. The **Prompt System** owns that transformation and, more importantly, owns **how prompts are composed, versioned, and evolved over the life of the product**.

The Prompt System is not a new runtime engine invented here; it is the discipline around the product's most quality-critical text. Its constitution is already established: prompt *bodies* live only in versioned repository files (ADR-013), composed by the deterministic block/budget assembler (ADR-009), emitted provider-neutral for a thin adapter to render (ADR-016), and regression-tested on the Bench (ADR-012). This RFC's job is to define the Prompt System as an architectural responsibility and lock its boundaries. It explains:

- **why the Prompt System exists** — why prompts are architecture, not implementation, and why prompt composition must be standardized;
- **what it owns** — prompt composition, versioning, the stage/facet prompt bodies, provider-neutral output, and budget-aware composition;
- **what it explicitly does NOT own** — knowledge storage, retrieval, extraction, generation, and human review.

It does **not** define any prompt's contents, any template, or any wording (§13).

---

## 2. Why the Prompt System Exists

### 2.1 Why prompts are architecture, not implementation

In this product, prompts are not incidental strings on the way to an API call — they are **where the creative behavior lives**. The governing rule of the whole architecture is that code written once (the loop runner, the Store, retrieval, the assembler) is *code*, while everything tuned weekly — *what to extract, how to plan, how to critique, how to style* — is a **versioned prompt file or a typed entry** (RFC-001 §2.4, §8.3). By that rule, prompts carry the product's most valuable and most volatile logic. Treating them as throwaway implementation detail would misplace the very thing that determines whether the output is web-novel-class or generic (ADR-009 §1). Prompts are therefore first-class architectural assets, and they need a system that treats them with the seriousness their impact warrants (§6; ADR-013 §5).

### 2.2 Why prompt composition must be standardized

The alternative to a standardized composition path is **ad-hoc string concatenation scattered across features** — each surface building its own prompt with format strings (ADR-009 §1, §4-A). That is the single most damaging failure mode in an AI-native system: unbudgeted, untestable, provider-coupled prompt-building that drifts between chat and novel and becomes impossible to reason about when output degrades (ADR-009 §1, §4-A). The Prompt System exists to make composition **one standardized, mandatory path**: every prompt is composed the same deterministic, budget-aware, provider-neutral way, so behavior is consistent across the product, diagnosable when it regresses, and robust across wildly different context windows (ADR-009 §2, §5). **No feature hand-assembles a prompt outside this system** (ADR-009 §2). Standardization is what turns prompts from a scattered liability into a governable asset.

---

## 3. Prompt System Responsibilities

The Prompt System's ownership is **prompt composition, versioning, and evolution**. This section defines *responsibilities* — high-level, **no block structures, no templates, no wording** (those are Defined in the corresponding RFC).

- **Prompt composition.** Combining the authored, versioned prompt bodies with assembled context into a single, coherent prompt, through the one standardized composition model (§5; ADR-009 §2). The Prompt System owns *how the pieces come together*, deterministically and once.
- **Prompt versioning.** Keeping every prompt body under version control — diffable, reviewable, rollback-able — as the single source of truth for that prompt (§6, §7; ADR-013 §2). The Prompt System owns the discipline that prompts are *files with history*, never database rows.
- **Prompt stages (and facets).** Holding the product's creative behavior as a library of prompt bodies — each Writer stage is a file, each Analyst facet is a file — that a declarative list selects among (ADR-013 §1; ADR-005 §2; ADR-008 §2). The Prompt System owns the bodies as assets; *which* stage or facet runs when is chosen by the Writer or Analyst that drives it (§9; RFC-004 §3; RFC-008 §8).
- **Provider abstraction (the neutral boundary).** Composing to a **provider-neutral** form and owning that neutrality — no provider quirk ever enters a prompt body or the composition (ADR-009 §4; ADR-016 §2). The Prompt System owns the neutral contract at its output; the thin **provider adapter** — owned elsewhere — renders that neutral form into a specific provider's call (§8-note; ADR-016). *The adapter is Defined in the corresponding RFC (the Provider Adapter RFC).*
- **Prompt budgeting (budget-aware composition).** Composing within the token budget so the result always fits, with the important material preserved and only the truncatable material trimmed (ADR-009 §2–§3). RFC-003 bounds the retrieved knowledge slice; the Prompt System owns the final whole-prompt budget guarantee.

Across all of these, the Prompt System owns **the form and lifecycle of prompts** — how they are built, versioned, and improved — not the *knowledge* they carry, the *truth* they draw on, or the *output* they produce (§4).

---

## 4. What the Prompt System Does NOT Own

The Prompt System's non-ownership is as binding as its ownership; ambiguity here re-creates the sprawl the architecture exists to prevent (RFC-001 §4). The Prompt System owns *prompts*, not knowledge, truth, or output.

- **Knowledge storage.** The Prompt System holds no persisted creative knowledge. All knowledge lives in the **Store** (RFC-002). Prompts *carry* knowledge into the model, but the knowledge belongs to the Store; a prompt body contains authored instruction, not stored truth (ADR-013 §3).
- **Retrieval.** The Prompt System does not select which knowledge enters a prompt. Selection is **Retrieval**, the Store's one capability (RFC-002; RFC-003). The Prompt System composes with whatever context assembly hands it; it does not choose that context.
- **Knowledge extraction.** The Prompt System does not turn text into knowledge. Extraction is the **Analyst's** job (RFC-008 §3). The Analyst's facets are prompt bodies the Prompt System versions — but *running* extraction, and owning its output, belongs to the Analyst.
- **Narrative generation.** The Prompt System does not generate prose. Producing draft fiction is the **Writer's** job, and calling the model is the provider adapter's (RFC-004 §3; ADR-016 §2). The Prompt System produces the *prompt*; it does not produce the *completion*.
- **Human review.** The Prompt System does not decide what becomes canon. The **review gate** governs knowledge (RFC-002; RFC-005 §5); prompt *bodies* are governed by code review and the Bench (ADR-013 §1), a separate discipline from the knowledge-canon gate. A prompt never writes canon.

The discipline: **the Prompt System composes and versions prompts; it never stores knowledge, selects it, extracts it, generates from it, or canonizes it.**

---

## 5. Prompt Composition Philosophy

Composition follows one standardized model, described here **conceptually** — without defining any block's contents, any template's wording, or the pipeline's algorithm (those are Defined in the corresponding RFC).

```
   prompt blocks    ── every piece of context is a discrete block
      │                 (with a kind, a role, a priority, a truncatable flag)
      ▼
   prompt template  ── the authored, versioned prompt body (a file)
      │                 that structures how blocks combine for a given step
      ▼
   final prompt     ── the deterministic, budget-fitted, provider-neutral
                        composition — rendered provider-ready by the adapter
```

- **Prompt blocks — context as discrete units, never concatenated ad hoc.** Everything that goes into a prompt is a block with an explicit kind, a target role, a priority, and a truncatable flag; context is *collected as blocks*, so composition can order and budget it deterministically (ADR-009 §2). Protected blocks — the user's message, the system instruction — are never dropped (ADR-009 §3). *The block structure is Defined in the corresponding RFC; this RFC does not define block contents.*
- **Prompt template — the authored, versioned body.** A template is the stable, human-authored prompt body — a system template, a Writer stage prompt, an Analyst facet — that expresses the creative instruction and structures how blocks combine for a given step (ADR-013 §1; ADR-005 §2; ADR-008 §2). Templates are the *product logic*; they live in versioned files (§6, §7). *This RFC does not define any template.*
- **Final prompt — deterministic, budgeted, provider-neutral.** Composing a template with its blocks yields the final prompt: fitted to budget by priority, reproducible given its inputs, and emitted in a provider-neutral form the adapter renders provider-ready (ADR-009 §2, §4). The composition is a function of its inputs — the same template and the same blocks compose the same final prompt.
- **User customization enters as inputs, never as body edits.** Where the author customizes behavior — a forbidden-expression list, a tone/theme contract, a reference-influence knob, an episode-length target — those are **structured inputs injected as blocks/variables**, never edits to a prompt body (ADR-013 §3). The composition model draws a hard line: bodies are authored product logic; user control is bounded input *to* composition (§6).

The philosophy in one line: **discrete blocks, an authored versioned template, one deterministic budgeted composition — the same way, every time, for every surface.**

---

## 6. Prompt as Architecture

This is the Prompt System's central thesis, and it is stated as a dedicated commitment: **prompts are architectural assets, and prompt files — not databases — are the primary source of truth.**

### 6.1 Why prompts are architectural assets, not ordinary text

Prompts carry the product's creative behavior — what to extract, how to plan, how to critique, how to style (RFC-001 §2.4). That places them at the same level of consequence as core code: a change to a prompt can lift or wreck output quality as surely as a change to an algorithm (ADR-009 §1). Assets of that consequence demand the guarantees code gets — history, diff, review, regression coverage, rollback (ADR-013 §5). Treating a prompt as an ordinary, editable text blob would strip it of exactly those guarantees and leave the product's most quality-critical logic un-versioned and un-reasoned-about. So the architecture treats prompts as **first-class assets**: each prompt body has git history, is diffed and reviewed like code, is Bench-regression-tested before it ships, and can be rolled back (ADR-013 §1, §5). Prompts are not a place text happens to live; they are a governed part of the architecture.

### 6.2 Why prompt files, not databases, are the primary source of truth

The decisive decision (ADR-013 §2): **prompt bodies live only in versioned repository files; there is no `prompt_templates` database table and no per-user prompt-body override.** Files are the primary source of truth for three reasons, each of which a database fails:

- **Files can be diffed, reviewed, and regression-tested; database rows rot invisibly.** DB-stored prompts cannot be diffed, cannot be code-reviewed, and cannot be Bench-tested as a unit of change — so they degrade silently, with no history of what changed or why (ADR-013 §1, §4-B). Files put prompts in the same review-and-measure workflow as everything else that matters.
- **One file per prompt means no drift and no fork matrix.** A database override tier forks prompt bodies per user into an unsupportable matrix and lets a stale override silently mask an improved base — the exact drift the architecture refuses (ADR-013 §1, §4-A). With bodies-in-files-only there is *one* source per prompt body, and the resolution question disappears (ADR-013 §5).
- **Files keep the product zero-cost, local-first, and offline.** An external prompt-management service or a DB tier adds dependency, cost, or network reliance that breaks the founding posture; files + git + the Bench deliver versioned, reviewable, regression-tested creativity with none of it (ADR-013 §4-D; RFC-001 §2.1).

The corollary — the line the whole decision rests on — is **bodies vs. inputs**: prompt *bodies* are product logic and live in files; *user customization* is structured inputs injected into prompts, never editable bodies (ADR-013 §3; §5 here). This keeps the source of truth singular and the user's control safe and bounded.

The thesis in one line: **a prompt is a versioned architectural asset with a single file-based source of truth — because the product's creative logic deserves the same rigor as its code, and a database gives it none.**

---

## 7. Prompt Versioning Philosophy

Following directly from §6, versioning is not a convenience but a requirement of treating prompts as architecture.

- **Prompts belong in version control.** Every prompt body is a repository file with full git history — authored on a branch, diffed, reviewed, merged (ADR-013 §1, §4-C). This is the same workflow the entire architecture is built around: creative behavior evolves as *commits to `prompts/`*, not migrations and not services (RFC-001 §2.4, §7). Version control is where prompts get the seriousness their impact warrants.
- **Evolution must be auditable.** Because prompts drive quality and change often, *what changed, when, and to what effect* must be recoverable. Version control supplies the "what and when"; the Bench supplies the "to what effect" (§9; ADR-012). Together they make prompt evolution an audited trail rather than a series of unattributable edits — so a quality regression can be traced to the change that caused it and reverted (ADR-013 §5; ADR-009 §7). Auditability is what makes prompt change *safe* to do often.
- **Maintainer tuning is a normal code-plus-Bench loop.** Editing a prompt is: edit the file → Bench-compare against the current version → commit if it wins (ADR-013 §4). Rapid experiments live on a branch or a local file, gated by measurement, then merged. There is no in-app prompt-body editor, deliberately — bodies are product logic (ADR-013 §5-Negative).
- **No drift, by construction.** With one file per prompt body and no database tier, there is no override to fall stale, no per-user fork to reconcile, no silent masking of an improved base (ADR-013 §2, §5). The versioning philosophy eliminates drift rather than managing it.

The philosophy in one line: **prompts live in git and prove themselves on the Bench — versioned, auditable, drift-free.**

---

## 8. Relationship with Retrieval

The Prompt System consumes retrieval output and owns standardized prompt composition; it does not perform Store selection (RFC-003).

- **Retrieval selects; the Prompt System composes.** Retrieval chooses the minimum necessary knowledge and supplies a traceable Entry-to-PromptBlock handoff (RFC-003). The Prompt System combines those blocks with non-knowledge inputs and the authored template through the ADR-009 assembly path.
- **The Prompt System never reaches into the Store.** It composes with whatever blocks assembly provides; it does not query the Store, hand-select knowledge, or re-rank — selection stays wholly in retrieval, keeping the boundary clean (RFC-003; ADR-009 §v2-note). If a prompt is missing knowledge, the fix is in retrieval, not in the prompt body inventing facts.
- **Composition preserves determinism and the final budget guarantee.** The ADR-009 assembler produces reproducible, budget-fitting prompts; RFC-003 independently guarantees deterministic selection within the caller's knowledge budget. These adjacent guarantees are tested together but remain separately owned.

*Note on the provider boundary:* the Prompt System's output is **provider-neutral**; rendering it into a specific provider's call is the thin **provider adapter's** job, where all provider quirks are quarantined (ADR-009 §4; ADR-016 §2). The Prompt System owns neutrality; it does not own the adapter. *The adapter is Defined in the corresponding RFC (the Provider Adapter RFC).*

---

## 9. Relationship with Writer

The Writer **drives** the Prompt System but **owns** neither the prompt bodies nor the composition (RFC-004 §3–§4).

- **The Writer selects which stage prompt runs; the Prompt System holds it.** Each Writer stage is a prompt body the Prompt System versions; the Writer's declarative stage list chooses which runs when (ADR-005 §2; ADR-013 §1; RFC-004 §3). The Writer owns the *orchestration* — the sequence of stages — while the Prompt System owns the *bodies* as versioned assets and the *composition* that builds each stage's prompt (§3; RFC-004 §4).
- **The Writer's craft lives in prompt bodies, not in its code.** RFC-004 is explicit: planning heuristics, critique criteria, serialization cadence, and style live in prompt files, not in the loop runner (RFC-004 §4, §9). Those files are exactly what the Prompt System owns and versions. The Writer's runner is written once; its craft evolves as prompt commits the Prompt System governs (RFC-001 §2.4).
- **The same standardized path serves the Writer and the Analyst and chat.** Writer stages, Analyst facets, and chat prompts are all composed the one standardized way — no per-surface prompt-building (ADR-009 §2, §4-A; RFC-008 §8). This is what keeps the product's behavior consistent across its capabilities. **This RFC does not redefine the Writer — RFC-004 does.**

The one-line boundary: **the Writer chooses and sequences prompt bodies; the Prompt System owns, composes, and versions them.**

---

## 10. Relationship with Bench

Prompt changes must **always be measurable** — this is the non-negotiable companion to putting creative behavior in constantly-changing files (RFC-001 §8.9; ADR-012).

- **Because behavior lives in prompts, behavior will change constantly.** The architecture deliberately concentrates creative logic in prompt files precisely so it can be tuned weekly (RFC-001 §2.4; ADR-013 §4). But constant change without measurement means week-6 "improvements" that silently break voice or continuity, discovered only when a reader hits them (`architecture-final-minimal.md` §7). The Bench exists to make that impossible.
- **Every prompt change is Bench-gated before it ships.** A prompt edit is A/B-compared against the current version on the golden scenarios, using the checks already built as metrics, before it is merged (ADR-012; ADR-013 §1, §4). This converts "did this prompt help or hurt?" from a vibe into a measurement (RFC-001 §8.9). No prompt body ships on intuition.
- **Measurability depends on deterministic composition.** The Bench can only attribute a quality change to a prompt change if composition is deterministic given fixed inputs (ADR-009). The Prompt System's deterministic, file-based, single-source composition is therefore the precondition that makes prompt evaluation meaningful. RFC-003 supplies the separately deterministic retrieved Entry set. **This RFC does not redefine the Bench — the corresponding RFC does.**

The one-line boundary: **the Prompt System makes prompts changeable and versioned; the Bench makes every change measurable — neither is safe without the other.**

---

## 11. Evolution Strategy

The Prompt System is designed so the product's creative behavior evolves for years without architectural change (RFC-001 §7).

- **New creative behavior is a new prompt file.** A new Writer stage, a new Analyst facet, a new critique, a new style behavior is a **new prompt body** added to a declarative list — no new engine, no schema, no service (RFC-001 §7.2; ADR-005 §2; ADR-008 §2; ADR-013 §1). The Prompt System absorbs it as another versioned asset. This is the cheapest, most-exercised evolution surface in the whole architecture.
- **Better behavior is a better file, proven on the Bench.** Improving a prompt is editing its file and Bench-comparing before merge (§7, §10; ADR-013 §4). The composition path, the versioning discipline, and the measurement loop all stay fixed; only the file's content changes.
- **New context sources are new block kinds, not new machinery.** When a new kind of knowledge should enter prompts, it becomes a new block with a priority in the existing composition model — absorbed without new assembly machinery (RFC-003; ADR-009 §5). The composition model was built to be the natural insertion point for every future context source.
- **Provider evolution stays in the adapter.** New providers or provider features are handled by the adapter's rendering while composition stays provider-neutral; the neutral contract is revisited only if a compelling capability genuinely cannot be expressed neutrally (ADR-009 §4-C, §6; ADR-016 §6). The Prompt System's core stays still while the provider landscape churns.
- **User customization grows as bounded inputs, never as body editing.** New customization surfaces are new structured inputs injected into composition — never new editable prompt bodies (ADR-013 §3, §6). If in-app body editing were ever genuinely needed, it would be a maintainer-only, still-file-authored mechanism — never a database tier that reintroduces drift (ADR-013 §6). *Any such mechanism is Defined in the corresponding RFC.*

---

## 12. Architectural Risks

The prompts-as-versioned-assets design is a strong bet; honesty requires naming its failure modes and the guard on each.

### 12.1 Can prompts become too large?

**Not in the final prompt — by invariant — but the risk is real upstream.** The composition budget guarantees the *assembled* prompt never overflows the context window, dropping only truncatable blocks and never the protected ones (ADR-009 §2–§3). RFC-003 separately constrains the retrieved knowledge slice. The honest residual risks are about *composition under pressure*, not overflow:

- **Priority tuning is a subtle craft.** What a template drops first when budget is tight is a real quality lever; wrong priorities silently hurt output (ADR-009 §5-Negative). The guard is Bench-measured priority tuning, not intuition (§10; ADR-009 §6).
- **Template bloat wastes budget.** An over-long prompt body crowds out the retrieved knowledge that actually lifts quality. The guard is the same code-plus-Bench discipline: a bloated template that does not measurably help does not merge (§7, §10; ADR-013 §4).

### 12.2 Can prompt drift occur?

**Not the database drift the architecture designed out — but human/version drift remains a risk to manage.** The unsupportable-matrix and silent-masking drift of DB overrides is eliminated by bodies-in-files-only with one source per prompt (§6.2; ADR-013 §2, §5). What remains:

- **Prompt-file sprawl.** As stages and facets accumulate, the file inventory can grow unwieldy (ADR-013 §5-Future-risks). The guard is the declarative stage/facet lists that make the active set explicit, plus the Bench pruning what does not earn its keep (ADR-013 §5; ADR-005 §2).
- **Silent behavioral drift between versions.** A prompt edit can subtly shift behavior in a way a human reviewer misses. The guard is that no edit ships un-measured — the Bench is the regression net that catches drift a diff alone would not (§10; ADR-012). Drift is caught by measurement, not trusted away.
- **Bodies edited outside the one path.** The rule "no feature hand-assembles prompts" must be *enforced*, or a "just this once" ad-hoc prompt reintroduces the scattered-string failure mode (ADR-009 §6-Future-risks). The guard is code review and a lint/test that keeps composition on the single path (ADR-009 §6).

### 12.3 How should prompt quality be evaluated?

**On the Bench, against frozen golden scenarios — never by intuition** (§10; ADR-012). Because prompts are the product's highest-leverage, most-changed text, their quality is evaluated by measurement: every change A/B-compared on golden scenes using the built-in checks as metrics, with deterministic retrieval (RFC-003) and deterministic composition (ADR-009) ensuring the result is attributable to the change. Priority tuning, if it becomes a recurring lever, is itself surfaced to the Bench so it is measured rather than guessed (ADR-009 §6). *The Bench is Defined in the corresponding RFC.*

### 12.4 When should prompt structure change?

**Rarely, and only when composition itself — not a prompt's content — is the limit.** The default is that behavior evolves by editing prompt *bodies* within the fixed composition model (§11); the *structure* (the block/priority model, the neutral contract, the pipeline) is deliberately the still part (ADR-009 §2). Structure changes only on a real, visible trigger:

- **The neutral contract changes** only if a widely-used, product-relevant provider capability genuinely cannot be expressed as neutral blocks — coordinated at the assembly↔adapter seam, keeping quirks in the adapter (ADR-009 §6; ADR-016 §6).
- **The composition/budget mechanism changes** only if measured over/under-budget behavior or a tokenizer limit demonstrably hurts — a tuning of the mechanism, not a redesign (ADR-009 §6). Retrieval-budget changes remain governed separately by RFC-003.
- **Structure never changes speculatively.** As everywhere in the architecture, a structural change waits for a concrete or Bench-measured trigger, not an anticipated one (RFC-001 §7.4).

---

## 13. Out of Scope

This RFC deliberately defines **none** of the following. Each is named so no later reader mistakes this document for defining it:

- **Prompt contents / wording** — the text of any system template, Writer stage, or Analyst facet. *Defined in the corresponding RFCs (the Writer Pipeline, Analyst-facet, and Prompt-content RFCs).*
- **Templates** — the concrete template format, the block schema, the composition pipeline's stages. *Defined in the corresponding RFC.*
- **Prompt blocks** — the concrete `PromptBlock` structure, kinds, final-assembly priority scheme, and truncatable semantics. *Defined by the Prompt Architecture implementation contract grounded in ADR-009; RFC-003 defines only the Entry-to-block handoff obligations.*
- **Models** — which model runs a prompt, provider or model selection. *Defined in the corresponding RFC (the Provider Adapter RFC).*
- **Algorithms** — the composition/budgeting/truncation procedure, variable resolution, caching by content hash. *Defined in the corresponding RFCs.*
- **Provider APIs** — provider-specific rendering, streaming normalization, retry/fallback, capability metadata. *Owned by the adapter; Defined in the corresponding RFC (the Provider Adapter RFC).*
- **Retrieval, assembly, generation, the Store, and the Bench** — owned by their respective RFCs; consumed or referenced here, not redefined.

Wherever this document needed such a detail, it wrote **"Defined in the corresponding RFC"** (naming the topic) and stopped, by rule.

---

## 14. Dependencies

RFC-009 depends on **RFC-001**, **RFC-002**, **RFC-008**, **RFC-004**, and **RFC-003** and must conform to them (and to the other completed RFCs); where they conflict, they govern (RFC-001 §10; and the dependency notes of the prior RFCs). The following areas of the system **depend on the Prompt System** defined here — they author its bodies, drive its composition, or measure its changes, and none may override the prompts-as-versioned-assets, files-are-source-of-truth, standardized-composition, always-Bench-measured boundaries established above:

| Depends on the Prompt System | Depends on it for |
|---|---|
| **The Prompt-content RFCs (Writer Pipeline, Analyst-facet)** | The versioned prompt bodies — stages and facets — whose contents realize the product's creative behavior. |
| **The Writer Pipeline & Scene/Episode RFC** | Selecting and sequencing stage prompt bodies the Prompt System composes and versions. |
| **The Analyst-facet RFC** | Facet prompt bodies versioned and composed the same standardized way. |
| **The Store-wide Retrieval RFC (RFC-003)** | The ordered, budgeted Entry selection and traceable PromptBlock handoff consumed by prompt composition. |
| **The Provider Adapter RFC** | Rendering the provider-neutral final prompt into a specific provider's call, quarantining quirks. |
| **The Bench RFC** | A/B-measuring every prompt change against golden scenarios before it ships. |
| **The Character Chat RFC** | Composing chat prompts through the same standardized, versioned path so chat and novel stay consistent. |
| **The Learning Capture & Distillation RFC** | Structured user inputs (forbidden list, tone contract, knobs) injected into composition — never body edits. |

> The forward references above are named by title rather than by number, because the prompts-as-architecture thesis, the files-are-source-of-truth rule, the single standardized composition path, and the always-Bench-measured discipline are what those RFCs build on regardless of final numbering. Their **dependence on versioned prompt bodies, standardized deterministic composition, and Bench-gated evolution is fixed**; where a successor and this RFC appear to conflict on those, this RFC — and behind it RFC-001 through RFC-003 and the ADR set — governs.

---

## Appendix A — Traceability

| RFC-009 Section | Primary sources |
|---|---|
| §1 Purpose | RFC-001 §2.4, §8.3; ADR-013 §2; ADR-009 §1; RFC-003 |
| §2 Why the Prompt System Exists | RFC-001 §2.4, §8.3; ADR-009 §1–§2, §4-A, §5; ADR-013 §5 |
| §3 Responsibilities | ADR-009 §2–§4; ADR-013 §1–§3; ADR-005 §2; ADR-008 §2; ADR-016 §2; RFC-003 |
| §4 Does NOT Own | RFC-001 §4; RFC-002; RFC-008 §3; RFC-004 §3; RFC-005 §5; RFC-003; ADR-013 §3; ADR-016 §2 |
| §5 Prompt Composition Philosophy | ADR-009 §2–§3; ADR-013 §1, §3; ADR-005 §2; ADR-008 §2; RFC-003 |
| §6 Prompt as Architecture | RFC-001 §2.4, §2.1; ADR-013 §1–§5; ADR-009 §1, §7 |
| §7 Prompt Versioning Philosophy | ADR-013 §1–§5; RFC-001 §2.4, §7; ADR-012; ADR-009 §7 |
| §8 Relationship with Retrieval | RFC-003–§8, §11; ADR-009 §4, §v2-note; ADR-016 §2 |
| §9 Relationship with Writer | RFC-004 §3–§4, §9; ADR-005 §2; ADR-013 §1; RFC-008 §8; RFC-001 §2.4 |
| §10 Relationship with Bench | RFC-001 §8.9; ADR-012; ADR-013 §1, §4; `architecture-final-minimal.md` §7; RFC-003 |
| §11 Evolution Strategy | RFC-001 §7, §7.2, §7.4; ADR-005 §2; ADR-008 §2; ADR-013 §1, §3, §6; ADR-009 §4-C, §5, §6; ADR-016 §6; RFC-003 |
| §12 Architectural Risks | ADR-009 §2–§3, §5–§6; ADR-013 §2, §5; ADR-012; RFC-003; RFC-001 §7.4 |
| §13 Out of Scope | RFC-001 §9 (RFC boundary conventions) |
| §14 Dependencies | RFC-001 §10; RFC-003 |

*End of RFC-009.*
