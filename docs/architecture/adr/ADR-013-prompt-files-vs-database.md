# ADR-013: Prompt Files vs Database

- **Status:** Accepted (revised v2 — **hardened**: prompt *bodies* live only in versioned files; v1's DB-override tier is dropped)
- **Date:** 2026-07-09 (v1) · revised 2026-07-09 (v2)
- **Deciders:** Architecture Review Board
- **Related:** ADR-001, ADR-005, ADR-008, ADR-010, ADR-012

## 1. Context

v1 decided a **hybrid**: base prompt templates as versioned files, *plus* per-user prompt-body **overrides in the DB** (files as fallback). Both reviews go further and reject the DB tier entirely:

> `architecture-final-minimal.md` §3: *"Prompts live in the repo, not the database. The old plan's `prompt_templates` table: delete the idea. DB-stored prompts rot invisibly, can't be diffed or reviewed, and fork per-user into an unsupportable matrix. Prompt files + git + the Bench = versioned, reviewable, regression-tested creativity. User-visible customization stays where you already put it: forbidden list, tone contract text box — inputs to prompts, never prompt bodies."*

Notably, this is the *exact* failure mode v1 itself flagged as the downside of DB overrides ("override drift: a user override can silently mask an improved base template"). The reviews resolve it cleanly by drawing the line at **prompt bodies vs. prompt inputs**: bodies are product logic (files); user customization is *structured inputs injected into* prompts (forbidden expressions, tone contract, reference-influence, episode length), never editable prompt bodies. Given the v2 architecture makes prompt files + Bench the core workflow (ADR-001/005/012), the hybrid's DB tier no longer earns its complexity.

## 2. Decision

**Prompt bodies (system templates, facet prompts, Writer stage prompts) live only in versioned repository files. There is no `prompt_templates` table and no per-user prompt-body override. User customization is limited to structured inputs that are injected into prompts.**

1. **All prompt bodies are files**, versioned in the repo (`prompts/…`), diffed, reviewed, and **Bench-regression-tested** (ADR-012). A facet = a file (ADR-008); a Writer stage = a file (ADR-005).
2. **No DB-stored prompt bodies.** The `design.md` `prompt_templates` table idea is **deleted** (it is on the two-year debt list, `architecture-final-minimal.md` §5). This *reverses v1's DB-override tier.*
3. **User customization = structured inputs, not bodies:** the personal **forbidden-expression list** (manual, permanent, user-owned), the **tone/theme contract** text box (ADR-004 R7), the **reference-influence** knob, and **episode target length** (ADR-020). These are *inputs to* prompt assembly (blocks/variables — ADR-009), never prompt-body edits.
4. **Maintainer tuning = edit the file → Bench compare → commit.** Rapid experiments happen on a branch/local file, gated by the Bench, then merged. This is the workflow the whole architecture is built around (ADR-001).
5. **The resolution question disappears.** v1 needed a file-vs-DB resolution order and had to warn about override drift; with bodies-in-files-only, there is one source for each prompt body — simpler and drift-free.

**Where the Board updates itself:** v1's hybrid was chosen to preserve user prompt-body customization. On re-examination — and prompted by both reviews — that customization is better served by structured inputs, and the DB tier introduced exactly the drift risk v1 itself disliked. The Board concedes the point and hardens to files-only. This **agrees with** `architecture-final-minimal.md`.

## 3. Alternatives Considered

- **A. v1 hybrid** — files for base, DB per-user prompt-body overrides.
- **B. DB-only** — the original `design.md` (all templates in `prompt_templates`).
- **C. Files-only for bodies + structured inputs for users** (adopted).
- **D. External prompt-management service.**

## 4. Why Rejected

- **A — Hybrid with DB overrides:** Introduces the "unsupportable matrix" (per-user forked bodies) and the silent-masking drift v1 flagged; the value (user body customization) is better delivered by structured inputs. Reversed.
- **B — DB-only:** Makes the product's most quality-critical text un-diffable, un-reviewable, un-Bench-testable, and un-rollbackable — and it *rots invisibly*. On the explicit debt list. Rejected (this was already rejected in v1; v2 also removes the DB tier that v1 kept).
- **C — Files-only + inputs:** Chosen. Bodies get git/diff/review/Bench; users still customize via inputs. Simpler than the hybrid.
- **D — External service:** Network dependency + cost; breaks Zero-Cost/Local-First/offline. Rejected.

## 5. Consequences

**Positive**
- Every prompt body has git history, diffing, review, Bench regression coverage, and rollback — treated with the seriousness its impact warrants.
- No drift risk, no per-user fork matrix, no seeding migration; one source per prompt body.
- Prompt tuning is a normal code+Bench workflow (ADR-001/012) — the intended evolution surface.
- User customization (forbidden list, tone contract, knobs) is clean, bounded, and safe.

**Negative**
- Editing a base prompt requires a code change/redeploy (the maintainer experiments on a branch/local file; there is no in-app body editor).
- Power users cannot rewrite raw prompt bodies — deliberately (it is product logic). Their control is via inputs.

**Future risks**
- If a genuine need for in-app body editing arises (unlikely for a personal tool), it would reintroduce the drift/matrix problem; handle via a maintainer-only mounted-file mechanism (still file-authored), not a DB tier.
- Prompt-file sprawl; mitigated by the Bench and declarative stage lists.

## 6. Future Revisit Conditions

- If hot-reloading file prompts without redeploy is needed for tuning speed, add a maintainer-only load-from-mounted-path mechanism — still files, still diffable.
- Revisit only if multi-user genuinely requires per-user prompt bodies (it would need a fresh answer to drift + the fork matrix; structured inputs remain preferred).
