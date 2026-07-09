# ADR-013: Prompt Files vs Database

- **Status:** Accepted — *hybrid: base/system prompt templates live as versioned files; user overrides live in the database. This revises `design.md`'s DB-only approach.*
- **Date:** 2026-07-09
- **Deciders:** Architecture Review Board
- **Related:** ADR-009, ADR-010, ADR-012, ADR-017

## 1. Context

Where should prompt templates live — in **version-controlled files** (part of the codebase) or in the **database** (editable at runtime)?

The existing `design.md` stores prompt templates entirely in the DB (`PROMPT_TEMPLATE` table, per-user, with `is_default`). This is a defensible default-looking choice, but the Board challenges it. Prompt templates are not ordinary user data — for this product they are **core product logic**. The structural system prompts that drive the Prompt Engine (ADR-009) are as consequential to output quality as source code, and they benefit from exactly the things files give you: git history, diffing, code review, testing, and rollback.

At the same time, the product promises user control ("Prompt 관리" in settings) and per-user customization, which argues for runtime-editable storage.

This is a genuine either/or with real trade-offs — hence a dedicated ADR.

## 2. Decision

**Adopt a hybrid, layered resolution: base templates as files, user overrides in the database, files as the fallback default.**

1. **Base/system prompt templates are version-controlled files** shipped with the app. They are the *authoritative defaults* for the Prompt Engine's structural prompts (chat system template, novel/continue template, summarization template, extraction template). They are reviewed, diffed, and tested like code.
2. **User customizations are stored in the database** as *overrides*, scoped per user (and per scope: chat/novel/summary). A user override, when present, takes precedence.
3. **Resolution order at assembly time:** user DB override (if any) → file default. Missing/blank user override falls back to the file. The Prompt Engine always has a valid template with no seeding migration required.
4. **The DB table becomes an override store, not the source of truth.** It holds only what the user chose to change — not a mandatory copy of every base template. (This *narrows*, not contradicts, `design.md`'s `PROMPT_TEMPLATE`: the table persists; its role shifts from "the templates" to "user overrides of the templates.")
5. **Bench fixtures and tuning target the files** (ADR-012): improving a base prompt is a code change with a diff and a Bench comparison, not an untracked DB edit.

> This ADR decides *where prompts live and how they resolve*. It does **not** write any prompt text (out of scope per the brief).

## 3. Alternatives Considered

- **A. DB-only** (the `design.md` status quo) — all templates, including defaults, in the database.
- **B. Files-only** — prompts are code; no runtime editing; users cannot customize.
- **C. Hybrid** (adopted) — files as default, DB as override.
- **D. External config store** (e.g. a prompt-management SaaS / remote config).

## 4. Why Rejected

- **A — DB-only:** Makes the product's most quality-critical logic **un-reviewable and un-diffable**. A change to the core system prompt would have no PR, no diff, no test gate, no rollback — it would be an opaque row edit. It also complicates fresh-clone startup (defaults must be seeded via migration/fixtures) and makes prompts invisible to the Bench-as-code discipline (ADR-012). For a multi-year, single-maintainer project, losing git history on the highest-leverage text in the system is a serious mistake. Rejected as the *sole* store (its role is preserved for overrides).
- **B — Files-only:** Removes user customization entirely, contradicting the product's "Prompt 관리" promise and the personalization ethos (ADR-010). Requiring a code edit + redeploy to tweak a prompt is too rigid even for a personal tool the user wants to experiment in. Rejected.
- **C — Hybrid:** Chosen. Keeps defaults reviewable/testable *and* lets users customize. The small added complexity (a resolution order) is well worth it.
- **D — External config store:** Adds a network dependency and a third-party service — violates Zero-Cost, Local-First, and offline operation (Ollama path). Rejected.

## 5. Consequences

**Positive**
- The core prompts get git history, diffing, review, test coverage, and rollback — treated with the seriousness their impact warrants.
- Bench-driven prompt tuning (ADR-012) becomes a normal code workflow (change file → compare → commit).
- Users retain full customization via DB overrides; defaults always exist (no seeding step; fresh clones just work).
- Clean separation: product logic (files) vs user data (DB).

**Negative**
- Two places to look for "the prompt in effect" (file default + possible DB override); the resolution order must be documented and obvious in the debug/trace view (ADR-009 §7).
- Editing a base prompt requires a code change/redeploy — less immediate than a DB edit for the maintainer (they can still use a DB override for quick experiments, then promote good ones to files).

**Future risks**
- Override drift: a user override can silently mask an improved base template (they won't get the upgrade). Mitigation: surface "you have a custom override; base default changed" and make reverting-to-default one action.
- If per-user override volume grows (multi-user future), the override store needs the same ownership scoping as everything else (Property 1) — already covered by ADR-017.

## 6. Future Revisit Conditions

- If multi-user (Phase 3) makes per-user prompt overrides common, revisit override management UX (compare against base, revert, share) — the storage split still holds.
- If a need arises to hot-reload base prompts without redeploy (rapid tuning), consider a maintainer-only mechanism to load file templates from a mounted path — still file-authored, still diffable.
- Revisit if a prompt ever needs to be *both* user-facing content *and* product logic (unlikely); handle by clearly classifying each template into one tier.
