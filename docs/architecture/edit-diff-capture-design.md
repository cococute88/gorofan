# Edit-diff capture persistence (P1-7 design proposal)

- **Status:** **Approved design — implementation not started.** Independently reviewed
  against the ADR/RFC set and the production call paths on 2026-08-09; the three items this
  document had left for ratification (§5.3, §9.2, §19-Q1) are decided, and every §19 open
  question is now RESOLVED or DEFERRED-WITH-SAFE-DEFAULT. No production code, ORM model,
  column, table, Alembic revision, or API exists for anything in this document.
- **Scope:** Where and when the system persists the difference between AI-produced text
  and the human's replacement of that text, so a later Analyst pass can distill it.
- **Governed by:** ADR-003, ADR-010, ADR-011, ADR-015, ADR-017; RFC-001 §5, §8.6, §8.8,
  §8.10; RFC-002 §4.2, §7.2, §7.3, §8.1, §8.2, §10; RFC-008 §5, §7, §10.3; RFC-011 §5, §6, §12.3.
- **Not an ADR, not an RFC.** This records the decisions an implementation must make
  inside the space the ADR/RFC set already fixed. Where it appears to conflict with an
  ADR or RFC, those govern and this document is in error. §21 explains why this is an
  implementation note rather than a new numbered document, and when that should change.

---

## 1. Status

| Item | Value |
|---|---|
| Task | P1-7 — edit-diff capture, day-one data collection |
| This deliverable | Persistence design + architecture review only |
| Design status | **Approved.** Independent architecture review, 2026-08-09 |
| Implementation | **Not started, and deliberately not started by this PR** |
| Current code | `ProvenanceSourceKind.EDIT_DIFF` exists in `backend/app/schemas/entry.py` as one enum value. Nothing computes, stores, or exposes a diff. |
| Alembic head | `0002_entry_store`, unchanged by this PR |
| Blocking on | **Nothing.** §7 (storage), §9 (transaction policy), and all eight §19 questions are decided. The next step is the separately approved implementation task. |

### 1.1 Decisions fixed by the independent review

The review verified each of these against the ADR/RFC originals **and** the executed
production paths, not against this document's own prose. The four schema/lifecycle
corrections it produced are folded into §6.3, §8, §10, §12, and §13 rather than left as
review commentary.

| Decision | Outcome |
|---|---|
| Entry vs non-Entry (§5) | **Non-Entry operational record.** Confirmed. |
| Storage (§7) | **Option 2 — one additive `edit_diff_captures` table.** Confirmed. |
| Escape-valve ratification (§5.3) | **Ratified.** A non-knowledge operational table does not consume the ADR-003 §6 promote-a-type valve. |
| Pre-image failure policy (§9.2) | **Ratified: atomic (policy A).** Capture failure rolls the destructive write back. |
| Path B settle trigger (§19-Q1) | **Resolved.** Next continuation on the write path, plus read-time resolution of the trailing row (§6.3, §13). |
| §19 Q2–Q8 | Resolved, or deferred with a safe default recorded here. None blocks implementation. |
| Corrections applied | `payload_state` split into orthogonal `before_state` / `after_state` (§8); Path B sequence derivation now requires an explicit chapter row lock (§10); ORM-relationship/`passive_deletes` hazard recorded (§12); trailing `pending` redefined as a normal terminal state (§6.3, §13). |

---

## 2. Problem

### 2.1 The architectural requirement

ADR-010 §2.2 makes edit-diff capture the one urgent item in an otherwise deferred
learning story: *"store draft text vs. accepted text … This is data that cannot be
recovered retroactively, so it is captured immediately even though the learning that
uses it is deferred."* RFC-001 §8.8 restates it as a hard constraint — *"Edit history is
captured immediately; distillation is a later, reviewable Analyst pass."* RFC-008 §5
repeats it for the Analyst's third input path and defers the substrate that records
diffs to "the Learning Capture RFC," which has never been written.

### 2.2 The concrete data loss happening today

This is not a theoretical gap. Two production paths destroy the AI original right now.

**Path A — Review Card edit.** `EntryService.edit_review_entry()`
([`entry_service.py:281`](../../backend/app/services/entry_service.py#L281)) assigns the
submitted fields onto the persisted row and commits:

```python
for field, value in dto.model_dump(exclude_unset=True).items():
    setattr(entry, field, value)
```

The AI-proposed `content` is overwritten in place. Nothing else in the schema holds a
copy. The Entry keeps `provenance.capture_method = "human-edited"` — a flag that an edit
happened — and no record of *what* it was before. Worse for reconstruction, the frontend
performs edit-then-accept as **two separate requests**
([`use-entry-review.ts:67`](../../frontend/src/hooks/use-entry-review.ts#L67)):
`editReviewEntry()` then `acceptReviewEntry()`. By the time the accept request runs, the
AI original is already gone from the database. **Any capture design that hooks the accept
call is capturing nothing.**

**Path B — Novel continuation.** `NovelService._append_chapter()`
([`novel_service.py:259`](../../backend/app/services/novel_service.py#L259)) concatenates
the streamed provider output straight into `Chapter.content_text` and re-derives
`content_doc`:

```python
new_text = (chapter.content_text + ("\n\n" if chapter.content_text else "") + text).strip()
```

The AI segment is merged into the author's document with no boundary marker. The moment
the author edits that chapter through `update_chapter()`, no query can recover which
characters the model wrote or what the author changed them to. This is the literal signal
ADR-010 §2.3 wants (sentence-length deltas, adverb rate, per-character particle fixes) and
it is being destroyed on every continuation.

### 2.3 What this design must produce

An additive, forward-only persistence design that captures both pairs at the moment they
exist, is cheap enough to run inside the request that would otherwise destroy them, does
not enter canon, does not enter retrieval, and does not commit the project to any
distillation machinery.

---

## 3. Architecture constraints

These are the rules the design is checked against, quoted or paraphrased from the
governing files rather than recalled.

| # | Constraint | Source | Consequence here |
|---|---|---|---|
| C1 | Capture is day-one; distillation is deferred. | ADR-010 §2.2–§2.3, RFC-001 §8.8 | P1-7 writes rows and stops. No facet, no `preference` Entry, no prompt change. |
| C2 | No ML training, no online learner, no opaque preference vector. | ADR-010 §2.1 | Captured rows are inert text, read only by a future human-reviewed pass. |
| C3 | "Learning" output must be visible, editable, revertible artifacts. | ADR-010 §2.1, §2.3 | Distillation output is `proposed` Entries through the review gate — not a capture-table side effect. |
| C4 | No AI-proposed change reaches canon except through human review. | RFC-001 §8.2, ADR-011 §2.6, RFC-011 §12.3 | Capture is a read-side-effect of a human action. It never writes, mutates, or promotes an Entry. |
| C5 | One knowledge model; governed closed `type` vocabulary; **no `misc`**, no parallel per-domain knowledge store. | RFC-001 §8.6, ADR-003 §2.3 | An edit diff must not become an Entry type. See §4 and §5. |
| C6 | Aggregates, operational records, and audit events are **not** Entries. | RFC-002 §4.2, ADR-003 §2.4 | The capture record is explicitly in RFC-002 §4.2's non-Entry list. |
| C7 | The one sanctioned structural escape valve is promote-a-type-to-a-table. | RFC-001 §8.10, ADR-003 §6, RFC-002 §10 | Applies to **knowledge** types. §5.3 argues why an operational capture table is not a promotion and does not consume the valve — this is the single point in this design that brushes a hard rule and needs explicit human ratification. |
| C8 | Migrations are additive and forward-only; `0001_initial` is frozen. | ADR-017 §2.7, ADR-015, RFC-002 §12.1 | New table only, in a new revision after `0002_entry_store`. Nothing existing is altered. |
| C9 | ORM-only, no raw SQL; single `DATABASE_URL` swap; SQLite↔PostgreSQL portable. | ADR-017 §2.1–§2.2 | Portable column types and constraints only. No JSON-path predicates, no dialect-specific cleverness. |
| C10 | `user_id` on aggregate roots; every query owner-scoped. | ADR-017 §2.3 | The capture table carries `user_id` directly and is never queried unscoped. |
| C11 | Review never blocks the creative flow (BR-6/BR-7); the user's own writing is never gated. | ADR-011 §2.2, RFC-011 §6, §12.3 | Capture adds no UI step, no round trip, no LLM call, no queue wait. §9 distinguishes this from "swallow all errors." |
| C12 | Provenance must not require storing an entire copyrighted source excerpt. | RFC-002 §8.1 | Bulk prose cannot live in `Entry.provenance`. Kills storage Option 1. |
| C13 | Supersession preserves history; hard delete is not ordinary correction. | RFC-002 §8.2 | Canon corrections are already fully recoverable through the supersession link and need no separate diff row (§5.2). |
| C14 | Retention of captured diffs stays "local and minimal." | ADR-010 §5-Future-risks | §12 bounds size and gives the owner an unconditional delete path. |

---

## 4. Definition of edit-diff

### 4.1 The capture predicate

An edit-diff capture is written **if and only if both** of the following hold:

> **(a)** A text produced by the AI and a text produced by the human *as a replacement for
> that same text* both exist at a single identifiable moment; **and**
> **(b)** completing the current write makes one of the two unrecoverable from the
> persisted schema.

(a) is what makes it a learning signal — a correction, not merely writing. (b) is what
makes it urgent — if the pair survives in the schema anyway, capture can wait and does not
belong in P1-7.

This predicate, not a list of endpoints, is the contract. It is what an implementation
reviewer should test a new call site against.

### 4.2 Path-by-path determination

| Lifecycle path | Capture? | Reasoning against §4.1 |
|---|---|---|
| `proposed → accept` (no edit) | **No** | Fails (a). There is no human replacement text. Acceptance without edit is an endorsement, which is a **review audit** fact (P1-9), not a correction signal. Capturing it would store a diff of a text against itself. |
| `proposed → edit → accept` | **Yes** | Both hold. The pre-image is destroyed by the edit write (§2.2 Path A). This is the canonical Entry-level correction signal. |
| `proposed → edit → reject` | **Yes, captured; excluded from distillation by default** | (a) and (b) hold at edit time, so the row is written — the capture point cannot know the future disposition. But an edit the human then rejected is not an endorsed correction, so the §13 read contract filters it out. Retaining the row costs almost nothing and keeps the option open. |
| `proposed → reject` (no edit) | **No** | Fails (a). A pure P1-9 audit fact. |
| Canon correction via `supersede()` | **No** | Fails (b). RFC-002 §8.2 already preserves the old canon as a `superseded` row linked by `superseded_by_entry_id`; the pair is queryable forever. It also usually fails (a): the replacement is a factual revision of already-human-approved canon, not a correction of AI output. See §19-Q3. |
| Direct user authoring (`create_user_authored`, no `supersedes_entry_id`) | **No** | Fails (a). There is no AI text. Capturing it would store the author's prose with nothing to compare it to — pure privacy cost, zero signal. |
| Human-first authoring anywhere | **No** | Same as above. |
| Novel continuation, AI segment appended | **Yes (draft side)** | (b) holds at append: merging into `content_text` erases the segment boundary (§2.2 Path B). The human side is resolved later — see §6.3. |
| Chat regenerate | **No** | Fails (b). `Message` rows are append-only and immutable (ADR-003 §2.4, ADR-017 §2.6); both the discarded and kept generations already persist. Nothing is lost by waiting, so this is out of P1-7's urgency scope. |
| Chat bookmark → `character.exemplar` proposal | **No (not in P1-7)** | Not implemented at all today. When it is, an edit to the resulting proposal is just the `proposed → edit → accept` row above; no new mechanism. |

### 4.3 The two signal families this produces

| Family | Pair | Feeds | Volume |
|---|---|---|---|
| **Knowledge correction** | AI-proposed Entry `content` → human's edited `content` | how the Analyst's extraction is wrong; later `user.preference` / extraction-facet tuning | small rows, low frequency |
| **Prose style correction** | AI continuation segment → the author's settled version of it | ADR-010 §2.5's three coarse signals (sentence length, adverb rate, per-character particle fixes); `style.preference` | large rows, one per continuation |

They are the same shape — *(before text, after text, what produced the before, which record
it belongs to)* — which is why §7 recommends **one** table with a discriminator rather than
two. They differ only in volume and in when the "after" side becomes known.

### 4.4 What an edit-diff is **not**

- Not the review actor, the action name, the action ordering, or reversal metadata. That is P1-9 (§16).
- Not a record of *every* Entry mutation. Only text pairs matching §4.1.
- Not a version history of a Chapter. `Chapter.version` already exists for optimistic concurrency and is not repurposed here.
- Not canon, not proposed knowledge, not retrievable, not prompt-visible.

---

## 5. Is an edit-diff an Entry?

**No. It is a non-Entry operational record.** This section is the argument, because
ADR-003's "everything is Entry" is the rule most likely to be misapplied here.

### 5.1 The four categories ADR-003 keeps apart

| Category | Definition | Where it lives | Example |
|---|---|---|---|
| **Creative knowledge** | An independently reviewable assertion or prompt-ready guidance, true within a scope (RFC-002 §4.1) | `entries` | `character.voice` — "그녀는 존댓말을 쓰지 않는다" |
| **Provenance** | Where one Entry came from and how it was captured (RFC-002 §8.1) | `entries.provenance` on that Entry | `{source_kind: "chapter", capture_method: "ai-extracted"}` |
| **Audit / event metadata** | Who did what, when, to which record | **Nothing today.** P1-9 decides. | "user X accepted entry Y at T" |
| **Learning signal** | Raw material for a future distillation pass; not yet an assertion about anything | **Nothing today.** This design. | "the model wrote A; the human made it B" |

An edit-diff is squarely the fourth. It asserts nothing about a character, a world, or a
story. It is not prompt-ready: injecting "the model wrote A and the human changed it to B"
into a generation prompt would be noise. It has no truth value to review. Making it an
Entry would require answering "what does it mean to *accept* this diff into canon?" — and
there is no coherent answer.

### 5.2 Testing it against the Entry contract

| Entry obligation | Would an edit-diff satisfy it? |
|---|---|
| `content` is non-empty prompt-ready prose (RFC-002 §13) | No. Its payload is a *pair* of texts, neither of them guidance. |
| Governed closed `type` from RFC-002 §6 | No member fits. Adding one would be exactly the vocabulary creep ADR-003 §5-Future-risks and §2.3 forbid, and there is no `misc` escape. |
| A `scope` that bounds applicability | Meaningless. A diff is not "true within" a work or a character. |
| Lifecycle `captured → proposed → canon` (RFC-002 §7.2) | Incoherent. Capture is mechanical; there is nothing for a human to approve, and RFC-011 §5 says the gate exists to confer *trust on knowledge*. |
| Retrieval eligibility (RFC-003) | Actively harmful. It would compete for the knowledge budget against real canon. |
| Provenance about itself | Circular — an edit-diff *is* provenance-adjacent data. |

Six failures out of six. It is not an Entry.

**And `note` is not the loophole.** RFC-002 §6 defines `note` as an *"intentionally
unstructured annotation that fits no stronger Phase 1 type"* that *"must still carry scope
and provenance."* It is a low-structure kind of **knowledge**, not a bucket for
non-knowledge — it is retrievable, reviewable, and prompt-visible like every other type. A
capture routed through `note` would inherit all six failures above and additionally pollute
retrieval. Using it here would be `misc` under a different name, which RFC-002 §6 forecloses
in the same paragraph.

### 5.3 Then why is a new table allowed?

Two rules could be read to forbid it, and both are about knowledge:

- **RFC-001 §8.6** — "One knowledge model … no parallel per-domain stores." A capture table
  is not a knowledge store: it is never retrieved into a prompt, never reviewed, never
  canon, and holds no assertion.
- **RFC-001 §8.10 / ADR-003 §6 / RFC-002 §10** — "the one sanctioned structural escape
  valve is promote-a-type-to-a-table … the single legitimate place a new table is added
  later." This clause governs the *knowledge* model: its five preconditions in RFC-002 §10
  are all about a deterministic consumer straining to parse Entry prose. None applies,
  because no Entry type is being promoted and no knowledge is moving.

Four things positively permit it:

0. **The architecture already classifies edit-diff capture as infrastructure, by name.**
   RFC-001's governing rule reads: *"Code that is written once — the loop runner, the entry
   store, the retrieval function, **edit-diff capture** — is code. Everything that will be
   tuned weekly … is a versioned prompt file or a typed entry."* ADR-015 §1 quotes the same
   sentence as its primary expansion principle. Edit-diff capture is listed alongside the
   entry store and the retrieval function — the substrate — and explicitly *opposite* the
   "new knowledge kind = a new `type` string" branch. The rule ADR-015 §1 is guarding
   against is a table named `dialogue_library` or `character_dna_attributes`: a **knowledge**
   library smuggled into a migration. `edit_diff_captures` is the other category the same
   sentence names.


1. **ADR-015 §2.2** states the rule for schema evolution directly: *"Non-destructive schema
   evolution … nullable columns / **new tables** via forward-only migrations; never break or
   repurpose existing structures."* New tables are a sanctioned non-destructive evolution.
   The escape-valve clause sits two items later in the *same* ADR (§2.5), scoped to *"when
   deterministic checks strain prose-first `data` JSON"* — which is what confirms the two
   clauses govern different things: §2.5 is about moving knowledge out of Entry, §2.2 is
   about adding structure that was never knowledge.
2. **RFC-002 §4.2** already enumerates the non-Entry residents of the schema — *"secrets,
   credentials, jobs, audit events, and review UI state"* and *"transient … operation-local
   working state"* — and ADR-003 §2.4 keeps true aggregates as typed tables. `0001_initial`
   is already full of such tables.
3. **The repository's own plan agrees.** `tasks.md` P1-7 says the diff capture table is
   *"Entry가 아닌 운영 기록이므로 aggregate로 취급"* ("an operational record, not an Entry,
   therefore treated as an aggregate").

What is *not* being done matters as much: no knowledge moves out of `entries`, no Entry type
is promoted, no second retrieval path appears, and nothing in the Store changes. RFC-002 §6's
warning that *"a new type does not justify a new table by itself"* is respected precisely
because no new type is proposed.

**Ratified (independent architecture review, 2026-08-09).** Adding a non-knowledge
operational table does **not** consume the ADR-003 §6 promote-a-type escape valve. The
valve's five preconditions in RFC-002 §10 are, without exception, statements about *a
deterministic consumer parsing Entry prose or bounded `data`* — "graph/timeline
reconstruction," "Entry remains the compatibility/retrieval boundary during migration."
None of them can even be evaluated for a record that was never an Entry and never enters
retrieval. The valve governs **moving knowledge out of `entries`**; ADR-015 §2.2 separately
and unconditionally sanctions **new tables** as non-destructive schema evolution, and
RFC-001 names edit-diff capture as substrate code (item 0 above). Because no ADR-level
decision is being made, this remains an implementation note rather than becoming an ADR
(§21).

### 5.4 Where Entries *do* appear in this story

Exactly once, and later: the P2-5 distillation pass reads captures and emits **`proposed`
Entries** — `style.preference` / `user.preference` — through the ordinary review gate
(ADR-010 §2.3). The vocabulary already anticipates this: RFC-002 §6 defines `user.preference`
as *"transparent author preference distilled from edits or supplied directly."* The type
exists; only the capture substrate that feeds it is missing. Those Entries carry
`provenance.source_kind = "edit-diff"`, which is what
the existing enum value is for. **The enum value describes the distillation output, not the
capture record.** P1-7 writes no Entry at all.

---

## 6. Capture lifecycle

### 6.1 Where the capture point must be

The capture point is forced by §2.2, not chosen: **the pre-image must be read and written
in the same request and the same transaction as the write that destroys it.** Any later
point is capturing a value that no longer exists.

| Candidate point | Verdict |
|---|---|
| At the edit request | **Correct for Path A.** The only moment both texts coexist. |
| At the accept request | **Impossible.** Edit and accept are separate HTTP requests (§2.2); the original is already overwritten. |
| At supersession | Not applicable — §4.2 shows supersession needs no capture. |
| Just before transaction commit (a session hook) | Rejected. An ORM flush hook would fire for every Entry mutation, cannot distinguish §4.1's predicate from an unrelated update, and buries a data-retention decision in framework middleware where no reviewer will find it. Explicitness beats cleverness for an irreversible schema. |
| Background job after the response | Rejected. The value is gone before the job runs. |

### 6.2 Path A — Entry review edit

```
POST /entries/review/{id}/edit
  └─ EntryService.edit_review_entry()
       1. _get_for_update()                    ← existing row lock
       2. require proposed                     ← existing
       3. read pre-image content                 NEW
       4. apply submitted fields               ← existing (destructive)
       5. set provenance.capture_method        ← existing
       6. if content changed: INSERT capture     NEW, same transaction
       7. commit                               ← existing, now covers 6
```

Properties:

- The row lock taken at step 1 already serializes concurrent edits of this Entry, so the
  `sequence` value assigned at step 6 needs no additional locking.
- Step 6 is skipped when `content` is unchanged (title/data-only edits, or a re-submit of
  identical text). A no-op diff is noise, and suppressing it also makes a duplicated
  request harmless (§10).
- A second edit of the same proposal writes a second row. The chain's first `before_text`
  is the pristine AI proposal; the last `after_text` at accept time is the canon content.
  Both endpoints of the pair are therefore always recoverable, and the intermediate steps
  are kept because "the author needed two passes" is itself signal.
- Only `content` is captured. `title` and `data` changes are recorded as field names in
  `context`, not as text pairs — they are audit facts (P1-9), and `data` may hold structure
  a text diff would misrepresent.

### 6.3 Path B — Novel continuation

Path B is harder because **the current chapter flow has no accept boundary at all.** The
author does not "accept" a continuation; the text is appended and they simply keep writing.
So the draft side and the settled side are captured at two different moments.

**Draft side — at `_append_chapter()`, same transaction as the chapter write.**
The streamed buffer is in hand and is about to lose its boundary. The row is written
unsettled (`settled_at IS NULL`): `before_text` = the AI segment, `after_*` unknown.
`context` records the insertion offset (`len(chapter.content_text)` before concatenation),
the resulting `chapter.version`, the prompt asset identity, and whether the stream ended
partially (the existing error path at
[`novel_service.py:251`](../../backend/app/services/novel_service.py#L251) appends a partial
buffer — those rows must be marked, because a truncated generation is not a style signal).

**Settled side — decided: the next continuation of the same chapter, and nothing else on
the write path.** At T1 of `_continue_impl()`, before any token is streamed, if the chapter
has an unsettled capture, write the chapter's current `content_text` as its `after_text` and
set `settled_at` and `context.settle_trigger = "next-continuation"`. Rationale:

- Requesting more prose is an unambiguous author signal that everything above it is what
  they want continued from. It is the closest thing to "accepted" the current UX has.
- It needs **no new UI, no new endpoint, and no new user gesture** — which C11 requires.
- It is deterministic and idempotent: one settle per capture row, guarded by
  `settled_at IS NULL`.
- It runs in a session the request already opens, next to the existing P1-6 Entry-context
  call, before streaming.

#### 6.3.1 The trailing unsettled row is a normal terminal state, not a gap

The obvious objection to that trigger — *the last continuation of a chapter is usually never
followed by another, so its row stays unsettled forever* — is real, and it is not a rare
edge: it is how every finished chapter ends. It is answered by observing what is actually at
risk.

**Only the before-side is irrecoverable.** The after-side is `chapters.content_text`, which
is a live, durable column that no capture path destroys. The settle snapshot therefore does
not *rescue* the after-side; its only job is **bracketing** — freezing the chapter as it
stood at the boundary between AI segment *N* and segment *N+1*, so segment *N*'s pair is not
contaminated by prose written after *N+1* arrived.

For the trailing segment there is no later boundary, so the correct bracket is *the chapter's
current state* — which a reader can obtain for free, at any time, forever:

> **Rule.** An unsettled `chapter-continuation` row whose chapter still exists is
> **complete**, not pending-in-error. Its after-side is defined as `chapters.content_text`
> resolved **at read time**, together with the row's stored `insert_offset` and
> `chapter_version`. §13 rule 2 makes such rows eligible; only rows whose chapter is gone or
> whose Work is soft-deleted are excluded.

This is why the alternatives are rejected rather than merely deferred:

| Alternative trigger | Verdict |
|---|---|
| Author's chapter save (`update_chapter`, the existing 1.2 s autosave in [`chapters/[chapterId]/page.tsx:84`](../../frontend/src/app/(main)/novels/[id]/chapters/[chapterId]/page.tsx#L84)) | **Rejected — it would poison the dataset.** The endpoint genuinely exists and fires on every edit, so coverage would be near-total. But the *first* save after an append lands ~1.2 s into revision, when the author has changed almost nothing. Settling there would systematically record "the human kept the AI text" for a corpus whose entire purpose is measuring how the human changes it. Missing data is honest; biased data is not. |
| Repeatedly refreshing the after-side on *every* save until some close event | Rejected. It makes an append-only table mutate on a 1.2 s timer, rewriting the full chapter text per keystroke burst, and it buys nothing that read-time resolution does not already give. |
| Explicit "finalize chapter" action | Rejected. It is new UX for a benefit read-time resolution already provides, and RFC-011 §6 warns against adding gates to the author's own writing. |
| Debounce timer after the last autosave | Rejected. Arbitrary, timer-dependent, and it settles at a moment with no product meaning. |
| Settle on chapter close | Not available. The frontend emits no close/unmount event, and no endpoint receives one. |

The remaining coarseness is honest and unchanged: a settled snapshot is the *whole* chapter,
not the isolated segment. Aligning segment to snapshot is a distillation-time problem, and
`insert_offset` + `before_sha256` + `chapter_version` are stored precisely so P2-5 can do it
(§13 rule 7). Choosing an alignment algorithm now would be the guess §8.4 already refuses to
make.

**Consequence for observability:** the §9.3 health counter must *not* treat unsettled rows as
a failure. A useful alarm is "unsettled rows on a chapter that has since received another
continuation" — that state is genuinely impossible unless the settle path is broken. A plain
count of unsettled rows measures how many chapters are still being written.

### 6.4 What never triggers capture

Generation with no human counterpart, reads, retrieval, prompt assembly, accept, reject,
supersede, direct authoring, chat streaming, and chat regeneration. Adding a call site
requires demonstrating §4.1.

---

## 7. Storage options and recommendation

Four options, each evaluated against the *actual* current schema
([`models/entry.py`](../../backend/app/models/entry.py),
[`models/novel.py`](../../backend/app/models/novel.py),
[`0002_entry_store.py`](../../backend/app/db/migrations/versions/0002_entry_store.py)).

### Option 1 — JSON on the existing Entry row (`provenance` or `data`)

Append a `edit_history` array to `Entry.provenance` (or `Entry.data`).

| Criterion | Assessment |
|---|---|
| Immutability | ✗ Worst possible. The row being mutated is the row that must preserve the pre-image; a bug in the same code path destroys both copies at once. |
| Lifecycle fit | ✗ Entry rows are living canon; captures are append-only history with a different retention need. |
| Queryability | ✗ Requires JSON-path predicates. SQLite JSON1 vs PostgreSQL JSONB semantics differ — violates C9's portability rule and ADR-017 §2.2. |
| Size | ✗ Unbounded growth on the hottest read path. Every `retrieve()` candidate row, every Review Card fetch, and every `EntryRead` response would carry the full prose history. |
| Migration | ✓ None required. The only advantage. |
| Portability | ✗ See queryability. |
| Analyst consumption | ✗ Cannot page or filter without a table scan plus JSON parsing. |
| P1-9 overlap | ✗ Invites an unversioned ad-hoc audit blob — precisely what [`review-card-api.md`](review-card-api.md) §"Intentional deferrals" forbids. |
| Retention / deletion | ✗ Cannot delete diffs without rewriting canon rows. |
| Transaction coupling | ✓ Trivially atomic. |
| Covers Path B? | ✗ **Fatal. Chapters are not Entries.** Half the requirement has nowhere to go. |
| C12 | ✗ Violates RFC-002 §8.1 — provenance must not carry whole source excerpts. |

**Rejected.** Two independent fatal defects (Path B, C12) plus a portability violation.

### Option 2 — One additive `edit_diff_captures` table (**recommended**)

An owner-scoped, append-only operational table with a `source_kind` discriminator serving
both paths.

| Criterion | Assessment |
|---|---|
| Immutability | ✓ Append-only by contract; only `after_*` / `settled_at` transition once, from NULL, guarded by a constraint. Matches the `Message` append-only precedent (ADR-017 §2.6). |
| Lifecycle fit | ✓ Independent of Entry status, Chapter version, and canon. |
| Queryability | ✓ Ordinary indexed columns; no JSON predicates. |
| Size | ✓ Bounded per row by §12, and physically separate from every hot read path. |
| Migration | ✓ One `create_table` + indexes. Additive, forward-only, touches nothing existing (C8). |
| Portability | ✓ Types already proven by `0002`: `String`, `Text`, `Integer`, `DateTime(timezone=True)`, portable `JSON`/`JSONB` variant, plain `CHECK`/`UNIQUE`. |
| Analyst consumption | ✓ Cursor pagination over `(created_at, id)`, exactly like `EntryRepository.list_page`. |
| P1-9 overlap | ✓ Cleanly separable: the table stores text pairs and no actor/action vocabulary (§16). |
| Retention / deletion | ✓ Rows deletable independently of canon; FK cascades give correct privacy behavior (§12). |
| Transaction coupling | ✓ One INSERT in the transaction the request already runs. |
| Covers Path B? | ✓ Yes — the whole reason for a discriminator. |
| Cost | New table (§5.3), plus one repository/service seam. |

### Option 3 — A new Entry `type` (e.g. `edit.diff`)

| Criterion | Assessment |
|---|---|
| C5 / vocabulary | ✗ Extends the closed RFC-002 §6 vocabulary for non-knowledge. ADR-003 §2.3 requires an ADR for a new type, and §5.2 above shows none of the type's obligations can be met. |
| Lifecycle | ✗ `captured → proposed → canon` is meaningless for a mechanical record. |
| Retrieval | ✗ Would compete for the knowledge budget; requires new exclusion rules across `retrieve()` and Context Assembly, i.e. new complexity in the most safety-critical path. |
| Content shape | ✗ One prose `content` cannot hold a *pair*; encoding both sides into one string is a private format inside a governed field. |
| Path B | ✗ No scope/subject combination fits "a segment of a chapter draft". |
| Immutability | ✗ Entry rows are mutable through the review path. |
| Migration | ✓ None. |

**Rejected.** It is the "everything is Entry" rule applied to something that is not
knowledge, and it damages the Store's core contracts to do it.

### Option 4 — Column pair on `Chapter` (ADR-010's literal wording)

ADR-010 §2.2 says *"one column pair on the substrate."* Taken literally: add
`draft_text` / `accepted_text` to `chapters`.

| Criterion | Assessment |
|---|---|
| Migration | ✓ Two columns, additive. |
| Simplicity | ✓ Simplest possible. |
| History | ✗ **Fatal.** A chapter receives many continuations; each would overwrite the previous pair. It captures the *last* diff and destroys the rest — reintroducing the exact loss P1-7 exists to stop. |
| Path A | ✗ No place for Entry-level corrections. |
| Size | ✗ Doubles the size of the hottest table on every read of `Chapter`. |
| Retention | ✗ Cannot delete captured prose without touching the author's document row. |
| Immutability | ✗ Mutable columns on a mutable aggregate. |

**Rejected**, and the divergence from ADR-010's wording is deliberate. ADR-010 is a
philosophy ADR; the substrate that records diffs is explicitly deferred elsewhere —
RFC-008 §5 states that *"capture timing and the substrate that records diffs are Defined in
the Learning Capture RFC,"* and ADR-003 §2 says of itself that it *"writes no columns, keys,
or DDL — those belong to an RFC."* The *decision* being honored is "capture the pair from
day one"; the column-pair phrasing is illustrative sizing, written before the Entry model
and the Review Card edit path existed. **§19-Q5 confirms this reading** — decisively, because
ADR-010 §2.2's column pair is scoped *"per chapter"* and so cannot express Path A at all.

### Recommendation

**Option 2 — a single additive `edit_diff_captures` table.** It is the only option that
covers both capture paths, keeps the capture physically and transactionally separable from
canon, stays portable under C9, gives retention and deletion a real handle, and leaves the
Entry contract untouched.

---

## 8. Proposed persistence schema

**Descriptive, not authored.** No model or migration is created by this PR. Names are
proposals; the implementation PR may refine them within this shape.

### 8.1 Table `edit_diff_captures`

Inherits the repository's `BaseModel` conventions (`id` `String(36)` UUID PK,
`created_at` / `updated_at` `DateTime(timezone=True)`) from
[`db/base.py`](../../backend/app/db/base.py).

| Column | Type | Null | Purpose |
|---|---|---|---|
| `id` | `String(36)` PK | no | UUID, `BaseModel` |
| `user_id` | `String(36)` FK `users.id` `ON DELETE CASCADE` | no | Owner scoping (C10), same shape as `entries.user_id` |
| `source_kind` | `String(32)` | no | `entry-review-edit` \| `chapter-continuation` |
| `entry_id` | `String(36)` FK `entries.id` `ON DELETE CASCADE` | yes | Set for `entry-review-edit` |
| `chapter_id` | `String(36)` FK `chapters.id` `ON DELETE CASCADE` | yes | Set for `chapter-continuation` |
| `sequence` | `Integer` | no | 0-based ordinal within one source; the idempotency anchor (§10) |
| `before_state` | `String(16)` | no | `stored` \| `oversize` — whether the before-text is retained (§11.2) |
| `after_state` | `String(16)` | yes | `stored` \| `oversize`; **NULL means not settled** |
| `before_text` | `Text` | yes | The AI-produced text, verbatim; NULL when `before_state='oversize'` |
| `after_text` | `Text` | yes | The human's replacement, verbatim; NULL while unsettled or `oversize` |
| `before_sha256` | `String(64)` | no | Lowercase hex of SHA-256 over the UTF-8 bytes |
| `after_sha256` | `String(64)` | yes | Same; NULL while unsettled |
| `before_chars` | `Integer` | no | Code-point length, retained even when `oversize` |
| `after_chars` | `Integer` | yes | Same; NULL while unsettled |
| `producer` | `String(120)` | yes | What generated the before-text, e.g. `novel.continue.v1` |
| `context` | portable `JSON`/`JSONB` | no | Bounded, documented keys only (§8.3); default `{}` |
| `settled_at` | `DateTime(timezone=True)` | yes | When the after-side was recorded; NULL while unsettled |
| `created_at`, `updated_at` | `DateTime(timezone=True)` | no | `BaseModel` |

> **Review correction — why there is no single `payload_state`.** The earlier draft used one
> `payload_state ∈ {stored, pending, oversize}`. That column conflated two **orthogonal**
> facts: *is the pair complete yet?* and *is the text retained or was it too large?* The
> conflation is not cosmetic — it made a legal row unrepresentable. A Path B row whose AI
> segment exceeds the cap is written at `_append_chapter` time as **both** oversize **and**
> not-yet-settled, and the earlier `ck_..._settled` constraint would have rejected it by
> demanding `settled_at IS NOT NULL` for any non-`pending` state. The two axes are therefore
> separate columns, and "pending" is not a state value at all — it is `settled_at IS NULL`
> (§6.3.1). This is exactly the class of mistake that is cheap to fix in a design document
> and expensive to fix in a shipped `0003`.

### 8.2 Constraints and indexes

```
CHECK ck_edit_diff_captures_source_kind
      source_kind IN ('entry-review-edit','chapter-continuation')

CHECK ck_edit_diff_captures_before_state
      before_state IN ('stored','oversize')

CHECK ck_edit_diff_captures_after_state
      after_state IS NULL OR after_state IN ('stored','oversize')

CHECK ck_edit_diff_captures_one_source          -- exactly one anchor
      (entry_id IS NOT NULL AND chapter_id IS NULL)
   OR (entry_id IS NULL AND chapter_id IS NOT NULL)

CHECK ck_edit_diff_captures_sequence            sequence >= 0
CHECK ck_edit_diff_captures_before_chars        before_chars >= 0
CHECK ck_edit_diff_captures_after_chars         after_chars IS NULL OR after_chars >= 0

-- text presence follows the retention state on each side, independently
CHECK ck_edit_diff_captures_before_payload
      (before_state = 'stored'   AND before_text IS NOT NULL)
   OR (before_state = 'oversize' AND before_text IS NULL)

CHECK ck_edit_diff_captures_after_payload
      after_state IS NULL
   OR (after_state = 'stored'   AND after_text IS NOT NULL)
   OR (after_state = 'oversize' AND after_text IS NULL)

-- settledness is one fact expressed by three columns; they move together
CHECK ck_edit_diff_captures_settled
      (settled_at IS NULL
         AND after_state IS NULL AND after_sha256 IS NULL AND after_chars IS NULL)
   OR (settled_at IS NOT NULL
         AND after_state IS NOT NULL AND after_sha256 IS NOT NULL AND after_chars IS NOT NULL)

-- only a chapter-continuation row may be unsettled (§6.3); Path A is born complete
CHECK ck_edit_diff_captures_entry_settled
      source_kind <> 'entry-review-edit' OR settled_at IS NOT NULL

UNIQUE uq_edit_diff_captures_entry_sequence     (entry_id, sequence)
UNIQUE uq_edit_diff_captures_chapter_sequence   (chapter_id, sequence)

INDEX  ix_edit_diff_captures_user_id            (user_id)
INDEX  ix_edit_diff_captures_owner_created      (user_id, created_at)
INDEX  ix_edit_diff_captures_owner_kind_settled (user_id, source_kind, settled_at)
```

All predicates use plain comparison, `IS NULL`, `IS NOT NULL`, `AND`/`OR`, and `IN` — no
`IS DISTINCT FROM`, no dialect functions, no expression or partial indexes. Every form above
parses identically on SQLite and PostgreSQL (C9).

The two `UNIQUE` constraints work without partial indexes because both SQLite and
PostgreSQL treat `NULL`s as distinct in a unique index: chapter rows all have
`entry_id IS NULL` and never collide there, and vice versa. This keeps the schema portable
under C9 with no dialect-specific `WHERE` clause. (PostgreSQL's `NULLS NOT DISTINCT` is
opt-in and must not be used.)

`ix_edit_diff_captures_owner_created` serves the §13 cursor scan; the leading columns of
the unique indexes serve the per-source lookups, so no separate `entry_id` / `chapter_id`
index is needed.

### 8.3 The `context` JSON — bounded keys only

`context` is a small, documented, closed set of scalars — **not** an open extension point,
and never a place for prose (C12 in spirit). Validation must reject unknown keys.

| Key | Paths | Meaning |
|---|---|---|
| `fields_changed` | A | Which editable fields the request touched (`["content","title"]`) |
| `asset_id`, `asset_version` | B | Prompt asset identity from `engines/prompt/assets.py` |
| `provider`, `model` | B | Provider-neutral identifiers of what produced the draft |
| `insert_offset` | B | Code-point offset in `content_text` where the segment was appended |
| `chapter_version` | B | `Chapter.version` after the append |
| `partial_stream` | B | `true` when the append came from the stream error path — **excluded from distillation** |
| `settle_trigger` | B | Which event settled the row. §6.3 defines exactly one write-path value: `next-continuation`. The key is absent while unsettled. It exists so that a future additional trigger is distinguishable in the data, not because one is planned. |

### 8.4 Format decision — full before/after text, not a structured diff

Candidates and the reasoning, against the Korean long-prose reality of §4.3's second signal family:

| Candidate | Verdict |
|---|---|
| `before_text` + `after_text` | **Chosen.** Every other representation is derivable from the pair; the pair is derivable from none of them. Reconstruction is exact by definition. |
| Unified diff | Rejected as the stored form. Lossy for the unchanged remainder, sensitive to line granularity, and Korean prose is frequently one paragraph per line — a one-word change produces a whole-paragraph hunk with no size saving. |
| `difflib` opcodes / patch JSON | Rejected. Ties an irreversible schema to one Python library's opcode encoding and its code-point indexing, which C9-style portability forbids. Offsets are also fragile across Unicode normalization forms and grapheme boundaries — a real hazard for Hangul, combining marks, and emoji. |
| Minimal hunks | Rejected. Same fragility, plus it presupposes the diff algorithm the future Analyst will want. Choosing that now is a guess. |
| Hash + compact diff (no full text) | Rejected as the sole form. A diff without a reconstructable base is unusable if the base row later changes. Hashes are kept **alongside** the text for integrity and dedup, not instead of it. |

Storage cost is not the constraint at personal scale: a Path A row is typically a few
hundred bytes, a Path B row a few tens of kilobytes, against §12's hard cap. Fidelity is
worth more than compression here, and any structured diff the Analyst wants can be computed
at read time from the pair — reversibly, and with whatever library is current then.

**Text is stored byte-exact, without normalization.** Normalizing would alter the author's
actual characters, and fidelity is the point. Consumers that compare strings should
normalize at read time; the schema does not depend on it. Note that `EntryCreate` /
`EntryReviewEdit` already `.strip()` content, so Path A captures the values as actually
persisted — which is correct: capture what the system stored, not what the wire carried.

---

## 9. Transaction and failure semantics

### 9.1 Reconciling "day-one capture" with "never block the author"

ADR-010 requires capture; ADR-011 §2.2 and `tasks.md` require capture failure not to break
the author's flow. These are reconciled by separating **cost** from **correctness**:

- **Non-blocking means:** no added user-visible step, no extra HTTP round trip, no LLM call,
  no job-queue wait, no UI gate, no confirmation. Capture is one INSERT into a local table
  in a transaction the request already performs. That is what C11 protects.
- **Non-blocking does not mean:** `except Exception: pass`. Silently discarding the only
  copy of an irrecoverable signal is the exact failure ADR-010 §4-C rejects, and it would be
  invisible — the system would appear to be capturing while collecting nothing.

### 9.2 The three-tier policy

| Tier | Data | Policy | Rationale |
|---|---|---|---|
| **1. Atomic** | The pre-image in Path A (§6.2 step 6) | **Same transaction as the destructive write. If the INSERT fails, the edit fails and rolls back.** No swallowing. | The pre-image exists nowhere else. A failed edit loses nothing — the proposal is untouched and the user retries. Failing loudly is strictly safer than succeeding while destroying data. This does not gate canon (C4): the accept path is untouched, and RFC-011 §12.3's "the user's own writing is never gated" concerns prose, not a knowledge-proposal edit. |
| **2. Atomic** | The draft side in Path B (§6.3) | **Same transaction as `_append_chapter`.** | The segment boundary is destroyed by the same statement. The existing partial-append error path is preserved unchanged; capture rides the transaction that is already required to be correct. |
| **3. Best-effort** | The settle/pairing snapshot in Path B (§6.3) | **May fail without failing the request.** Must log a structured warning with `request_id`, increment a counter, and leave the row unsettled so a later continuation — or read-time resolution (§6.3.1) — completes it. | The after-side still exists in `chapters.content_text`; nothing is lost by retrying, and §6.3.1 makes an unsettled row readable anyway. This is the one genuinely optional piece, and it is optional *because* the data survives — not because failures are convenient to ignore. |

**Ratified (independent architecture review, 2026-08-09): policy A — atomic — is correct,
and the alternatives are worse.** Verified against what each failure actually costs the
author in the real code:

- **Tier 1 (Path A).** A failed edit leaves the AI proposal untouched, and the author's typed
  replacement is still in React local state (`editContent` in
  [`review-card.tsx:109`](../../frontend/src/components/review/review-card.tsx#L109)), with
  the error surfaced through the existing `actionError` path. Nothing the human wrote is
  lost; they press the button again. Under best-effort, the same failure destroys the AI
  original permanently and reports success.
- **Tier 2 (Path B).** A rollback means the generation the author just watched stream is not
  persisted; `reloadFromServer()` then restores the pre-generation text and the segment
  visibly disappears. That cost is real and must be stated plainly to whoever implements it
  — but re-requesting a continuation costs one call and destroys nothing the author wrote,
  whereas the alternative silently merges the segment with its boundary erased, which is the
  precise loss P1-7 exists to stop.
- **Implementation note for the error branch.** `_append_chapter(..., partial=True)` is
  invoked from inside the `except` block at
  [`novel_service.py:251`](../../backend/app/services/novel_service.py#L251). A capture
  failure there must not mask the original provider error; the provider error is the one the
  author needs to see. Chain or log the capture failure, and still emit the provider error
  event.
- **Option C (a durable queue/outbox) is rejected for Phase 1.** ADR-015 §2.4 lists
  `JobQueue` as a *seam whose second implementation is deliberately not built* until a
  concrete trigger fires. An outbox would add a table, a writer, a drainer, and a retry
  policy to make a single local INSERT — in a transaction the request already opens — more
  reliable than the write it is protecting. It cannot be more reliable than that write: if
  the INSERT fails, the outbox insert in the same transaction fails identically. It is
  strictly more machinery for strictly no additional durability.

The dividing rule, stated once: **capture that holds the only copy is atomic with the write
that would destroy it; capture that duplicates surviving data is best-effort and
retryable.**

### 9.3 Failure observability

- Structured logs go through the existing `core/logging.py` JSON logger with `request_id`.
- **Log the failure, never the payload.** No captured prose, no hash-to-text mapping, and no
  excerpt in any log line or error response. Log `capture_id`, `source_kind`, source id,
  `sequence`, sizes, and the exception type. This extends an existing rule rather than
  inventing one: `core/logging.py` already documents that *"Secrets/plaintext keys/prompt
  bodies are never"* logged. Captured author prose joins that list.
- Tier-1 failures surface as ordinary API errors; they must not be reported as a partial
  success.
- The health signal for Tier 3 is **an unsettled row on a chapter that has since received a
  later continuation** — a state that is impossible unless the settle path is broken. A bare
  count of unsettled rows is *not* an alarm: per §6.3.1 it counts chapters still being
  written.

### 9.4 Explicitly forbidden

- `try: capture() except Exception: pass` anywhere.
- Capture in a background task, an `after_commit` hook, or a fire-and-forget coroutine for
  Tiers 1–2.
- Any capture call that can mutate, promote, or block an Entry lifecycle transition.
- Any new provider call, embedding, tokenization, or diff computation on the request path.
  Capture is I/O of text already in memory.

---

## 10. Idempotency

| Mechanism | Behavior |
|---|---|
| `UNIQUE (entry_id, sequence)` / `UNIQUE (chapter_id, sequence)` | The database-level guarantee. A replayed write cannot create a duplicate ordinal. |
| `sequence` derivation | Computed inside a transaction that **already holds a row lock on the source**: `MAX(sequence) + 1` for that source, or `0`. See the correction below — Path A satisfies this today; Path B does not and the implementation must add the lock. |
| No-op suppression | `before_sha256 == after_sha256` writes no row. A duplicated identical edit request is therefore inert. |
| Settle guard | The settle update is conditional on `settled_at IS NULL`. A second settle attempt affects zero rows and is not an error. |
| No client-supplied key | Capture is a server-side effect of a human action, never a client-addressable resource. Introducing a client idempotency key would create an API surface P1-7 must not have. |

A unique-violation on insert is a **bug signal**, not a retry path: it means two writers
believed they held the same source lock. It must raise, not be swallowed.

### 10.1 Review correction — Path B does not hold the lock this design assumed

The earlier draft asserted that "Path B holds the chapter row it is updating." **It does
not.** `NovelService._owned_chapter()`
([`novel_service.py:309`](../../backend/app/services/novel_service.py#L309)) loads the row
with a plain `session.get(Chapter, chapter_id)` — there is no `with_for_update()` anywhere in
the Novel service. The only serialization on the continuation path is `_active_continue`
([`novel_service.py:198`](../../backend/app/services/novel_service.py#L198)), a
**module-level in-process set**, which does not survive multiple Uvicorn workers and is not a
database lock at all.

Consequence if implemented as drafted: two concurrent continuations of one chapter can both
read `MAX(sequence)` before either commits, both compute the same ordinal, and the second
INSERT hits `uq_edit_diff_captures_chapter_sequence`. Under §9.2 Tier 2 that unique violation
raises, and the chapter append rolls back — so a race in the *capture* bookkeeping would
discard the author's generated prose. That is the wrong failure for the wrong reason.

**Required by this design, and an acceptance criterion (§20.24):** `_append_chapter()` must
load the chapter with an explicit `with_for_update()` — mirroring
`EntryRepository.get_for_update()`
([`entry_repository.py:24`](../../backend/app/repositories/entry_repository.py#L24)) — before
deriving the sequence, and must hold it through the INSERT and the chapter update. The same
lock must be taken by the §6.3 settle path. On PostgreSQL this serializes the two writers; on
SQLite the clause is ignored and single-writer semantics already hold (ADR-017 §2.1). This is
the existing, proven pattern in this repository, not a new mechanism.

Path A needs no change: `edit_review_entry()` already calls `_get_for_update()`
([`entry_service.py:289`](../../backend/app/services/entry_service.py#L289)), which does emit
`FOR UPDATE` on the Entry row.

---

## 11. Retention and size limits

### 11.1 Size cap

- `EDIT_DIFF_MAX_CHARS = 100_000` **per side** (code points). A long Korean web-novel
  chapter runs roughly 5,000–10,000 characters, so this is more than an order of magnitude
  of headroom while bounding a pathological paste. Worst case ≈ 300 KB UTF-8 per row for
  both sides; a typical Path A row is a few hundred bytes.
- The constant lives in code, not in the schema, so it can be raised without a migration.
  **The number is a configuration default, not a schema contract.** No column length, CHECK,
  or index depends on it; `before_state` / `after_state` record only the *outcome* of the
  comparison, never the threshold. Rows written under one value therefore remain valid and
  correctly interpretable after the constant changes, and changing it is a code edit with no
  `0003` amendment and no data migration. 100 000 is chosen for headroom against a realistic
  Korean web-novel chapter (~5 000–10 000 characters), not because the architecture depends
  on that figure.

### 11.2 Oversize handling — never truncate

If a side exceeds the cap, that side is written with its state column set to `'oversize'` and
its text column **NULL**, while its `*_sha256` / `*_chars` are retained. The two sides are
evaluated independently: an oversize before-text does not force the after-text to be
discarded, and vice versa (§8.2).

Truncation is prohibited, and this is a correctness decision rather than a storage one: a
diff computed from a truncated pair looks complete and is wrong. It would report deletions
the author never made at the truncation point, and it would silently bias any style
statistic toward chapter openings. A row that honestly says "this pair was too large to
keep" is analyzable; a quietly truncated one poisons the dataset the whole feature exists
to build. **§19-Q4 confirms oversize rows are kept.**

### 11.3 Retention policy

- **Default: retained indefinitely**, consistent with ADR-010 §2.2 (the data cannot be
  recollected) and §5-Future-risks (*"retention stays local and minimal"* for a personal,
  local-first tool).
- Distillation does **not** delete what it consumes; a re-run must be possible, and P2-5
  output is reviewable and revertible (C3).
- No automatic time-based expiry in P1-7. Any expiry policy is a product decision that
  belongs with the P2-5 distillation UX, not with capture. **§19-Q6 confirms this: indefinite
  retention, no ceiling.**
- Volume estimate for sanity: one continuation per writing session at ~10 KB, plus a handful
  of Path A rows, is single-digit megabytes per year at personal scale.

---

## 12. Privacy and deletion

Captured rows contain the author's unpublished creative writing — the most sensitive data
in the system. The design treats deletion as a first-class requirement, not an afterthought.

| Event | Behavior | Reason |
|---|---|---|
| User deleted | `ON DELETE CASCADE` from `users.id` | Matches `entries.user_id`. No orphan prose survives an account deletion. |
| Chapter hard-deleted | `ON DELETE CASCADE` from `chapters.id` | `NovelService.delete_chapter()` performs a real delete. Deleting a chapter must take its captured drafts with it — the author's clear intent is that this text is gone. Preferred over `SET NULL`, which would leave unattributable prose behind. |
| Entry deleted | `ON DELETE CASCADE` from `entries.id` | Entries are not hard-deleted today; the cascade is correct if that ever changes. |
| Work **soft**-deleted | Rows retained; **excluded from all §13 reads** | Soft delete is reversible (ADR-017 §2.4), so destroying data would be wrong. Exclusion mirrors the Entry orphan-anchor rule (RFC-002 §4.3) already implemented in `_exclude_orphaned_candidates()`. |
| Owner requests deletion | Unconditional hard delete of the selected rows | The table has no dependents; nothing references a capture. Deleting captures must never affect canon, chapters, or Entry history. |
| Export | Captures are **excluded by default** from any future JSON export | They are internal telemetry about the author's process, not their work product. Opt-in only. |

All four cascade/soft-delete behaviors above were verified against the code, not assumed:
`Work` carries `SoftDeleteMixin` and `delete_work()` soft-deletes; `Chapter` does **not**, and
`delete_chapter()` performs a real `session.delete()`; `entries.user_id` is an
`ON DELETE CASCADE` FK to `users.id`; and SQLite runs with `PRAGMA foreign_keys=ON`
([`db/session.py:61`](../../backend/app/db/session.py#L61)), so the cascades are enforced on
both engines.

> **Review correction — the cascades must stay at the database level.** `delete_chapter()`
> issues an ORM `session.delete(chapter)`. If the implementation declares a SQLAlchemy
> `relationship()` from `Chapter` (or `Entry`, or `User`) to the capture rows **without**
> `passive_deletes=True`, SQLAlchemy's default behavior is to load the children and *null out
> their foreign key* instead of letting the database cascade. Because `chapter_id` is
> nullable, that would not raise — it would silently leave the author's captured prose in the
> table as an unattributable orphan, violating both §12's deletion contract and
> `ck_edit_diff_captures_one_source`. **Rule:** declare no ORM relationship to
> `edit_diff_captures` at all, or declare it with `passive_deletes=True`. The DB-level
> `ON DELETE CASCADE` is the mechanism. This is an acceptance criterion (§20.25).

Additional rules:

- Owner scoping is mandatory on every query (C10). There is no cross-user or unscoped read.
- No `work_id` is denormalized onto the table. Excluding soft-deleted Works (§13 rule 4) is a
  read-time join — `chapters → works` for Path B, and the Entry's own scope anchor for
  Path A, which `_exclude_orphaned_candidates()` already resolves. Adding a fifth
  denormalized column to avoid one join would create a consistency obligation for no measured
  benefit.
- Captured text is never returned by an existing API. P1-7 adds **no HTTP endpoint at all**;
  §13's contract is a service-level read used by a future in-process pass. Any future UI
  exposure is a separate decision.
- Captured text never enters a prompt, a log line, an error message, a trace, or a Bench
  fixture.

---

## 13. Future Analyst read contract

P1-7 captures. It does not consume. This section fixes only the minimum needed so P2-5 does
not have to re-litigate the schema — a query shape, not a pipeline.

```
list_edit_diff_captures(
    session, user_id, *,
    source_kinds: list[str] | None = None,
    since: datetime | None = None,
    page: PageParams,               # existing cursor pagination
) -> Page[EditDiffCapture]
```

Contractual obligations:

1. **Owner-scoped.** `user_id` is required and injected by the caller, exactly as
   `EntryRetrieveRequest` does today.
2. **Complete pairs only — with the after-side resolved, not merely stored.** A row is
   eligible when `before_state = 'stored'` and an after-side is obtainable:
   - `settled_at IS NOT NULL AND after_state = 'stored'` — the snapshot case; or
   - `settled_at IS NULL AND source_kind = 'chapter-continuation'` and the chapter still
     exists — the trailing-segment case of §6.3.1, where the after-side is
     `chapters.content_text` read live and the row is returned with
     `after_source = "live-chapter"` so the consumer knows it is a read-time value.

   `oversize` sides and rows with a missing chapter are excluded unless maintenance tooling
   asks for them. **`settled_at IS NULL` is not by itself an exclusion**; treating it as one
   would silently drop the final segment of every chapter, which is the systematic loss
   §6.3.1 exists to prevent.
3. **Endorsed corrections only.** For `entry-review-edit`, exclude rows whose Entry never
   reached `canon` (§4.2). For `chapter-continuation`, exclude `context.partial_stream = true`.
4. **Live anchors only.** Exclude rows whose Work is soft-deleted (§12).
5. **Deterministic order.** `(created_at, id)` ascending, cursor-paginated — the same
   `PageParams` / `encode_cursor` seam the Entry repository already uses.
6. **Read-only.** The Analyst never writes, updates, or deletes a capture. Distillation
   output is `proposed` Entries through the review gate (§5.4). Nothing in P2-5 may mark a
   capture "consumed"; re-runs must be possible.
7. **No structured diff is promised.** The contract returns the text pair. Any opcode,
   hunk, or statistic is computed by the consumer at read time (§8.4).

**Not part of this contract and deliberately undecided:** batching strategy, scheduling,
facet prompt shape, which statistics get extracted, and how a distilled `preference` Entry
is scoped. All belong to P2-5 (ADR-010 §2.3, RFC-008 §10.3's "distill later, not
continuously").

---

## 14. Migration plan

**No migration file is authored by this PR.** This is the intended shape.

| Item | Value |
|---|---|
| Revision id | `0003_edit_diff_capture` (matches the `000N_<snake_case>` convention of `0001_initial`, `0002_entry_store`) |
| `down_revision` | `0002_entry_store` |
| `branch_labels`, `depends_on` | `None`, as in `0002` |
| Head after | `0003_edit_diff_capture` |

**Upgrade shape**

1. `op.create_table("edit_diff_captures", ...)` with the columns, `CHECK`s, and FKs of §8.
2. `op.create_index(...)` for the three indexes and two unique constraints of §8.2.
3. Nothing else. No `ALTER` on `entries`, `chapters`, or any `0001` table.

**Downgrade**

`op.drop_table("edit_diff_captures")`. It exists to satisfy the round-trip assertions in
`tests/integration/test_migrations.py`, not as an operational procedure: ADR-017 §2.7 and
ADR-015 make migrations forward-only in practice, and running this downgrade against real
data destroys unrecoverable captures.

**Portability**

- Reuse `0002`'s `sa.JSON().with_variant(postgresql.JSONB(), "postgresql")` helper for `context`.
- `String` / `Text` / `Integer` / `DateTime(timezone=True)` behave identically on both engines.
- `CHECK` constraints use plain SQL boolean expressions with no dialect functions.
- No partial indexes, no `NULLS NOT DISTINCT`, no expression indexes (§8.2).
- SQLite runs with `PRAGMA foreign_keys=ON` (ADR-017 §2.4), so the cascades in §12 are real
  on both engines.
- Named constraints throughout, so SQLite batch-alter remains possible for any future change.

**Existing rows and backfill**

**None, and none is possible.** Every pre-existing edit already destroyed its pre-image
(§2.2). A backfill would have to invent the AI original — fabricating the exact signal the
feature is meant to measure. The table starts empty by design; this is the cost of the gap
having stayed open, and it is why the design should be ratified promptly.

---

## 15. P1-9 boundary

P1-7 and P1-9 both look at the review path, and letting them blur would produce an
unversioned ad-hoc audit blob — the outcome [`review-card-api.md`](review-card-api.md)
§"Intentional deferrals" explicitly rules out.

| | **P1-7 — edit-diff capture** | **P1-9 — review audit persistence** |
|---|---|---|
| Question answered | *What did the AI write, and what did the human make of it?* | *Who did what, when, to which Entry, and can it be undone?* |
| Trigger | Only §4.1 text pairs | Every review action, including accept and reject with no edit |
| Payload | Two texts + hashes + sizes | Actor, action, timestamp, target, reversal metadata |
| Purpose | Future learning signal (ADR-010) | Accountability and reversibility (ADR-011 §2.4) |
| Consumer | The P2-5 Analyst facet | The user, audit views, undo |
| Covers Path B (chapters)? | Yes | No — chapters have no review gate |
| Status | This design | Undecided (`implementation-status.md` G10) |

**Rules that keep them apart:**

1. P1-7 defines **no** actor vocabulary and **no** action vocabulary. `user_id` is present
   only for ownership scoping, as ADR-017 §2.3 requires of every table.
2. P1-7 writes **no** row for accept, reject, or supersede. If the capture table ever grows
   an "accepted with no edit" row, the boundary has been violated.
3. P1-7 is **not** the review history. A reader must not be able to reconstruct the review
   timeline from it, and no feature may come to depend on it for that.
4. When P1-9 lands, a capture row **may** gain a nullable FK to a review-event row. P1-7
   must not pre-invent that column, that table's name, or its vocabulary.
5. Conversely, P1-9 must not store text pairs. If it needs the before/after content, it
   joins to this table.

P1-7 does not block P1-9 and does not presume its outcome.

---

## 16. Non-goals

P1-7 does **not** do any of the following, and an implementation that does has exceeded its
approval:

- Distillation, preference learning, style analysis, or any statistic over captures.
- Prompt adaptation, model selection changes, fine-tuning, embeddings, or any ML.
- Any automatic canon write, Entry creation, Entry mutation, or status transition.
- Any change to `retrieve()`, ranking, Context Assembly, prompt blocks, or the P1-6
  contract (`DEFAULT_PRIORITY["entry"] = 65`, `LAYER_ORDER`, the 0.15 budget ratio, flag
  semantics, the propagate-don't-swallow retrieval error policy). Those are settled.
- Any HTTP endpoint, request/response DTO, or frontend change.
- Retroactive backfill of diffs that were never captured (§14).
- P1-8 legacy equivalence, or turning `FEATURES["entry_store_context"]` on.
- P1-9 review audit persistence (§15).
- Analyst, Writer, Story Bible, Character Chat, or Bench work.
- Modifying `0001_initial`, `0002_entry_store`, or the local `backend/data/app.db`.

---

## 17. Test plan for the implementation phase

Written now so the implementation PR cannot define its own success criteria after the fact.

**Migration** — `tests/integration/test_migrations.py`
- Chain `0001 → 0002 → 0003` applies on a fresh isolated SQLite database.
- `0003` compiles for the PostgreSQL dialect (the existing `test_initial_revision_compiles_for_postgresql` pattern).
- Round-trip up/down leaves no residue.
- `entries` and `chapters` DDL are byte-identical before and after `0003`.

**Capture — Path A**
- Edit that changes `content` writes exactly one row; `before_text` equals the pristine AI proposal.
- Edit that changes only `title` / `data` writes **no** row and records `fields_changed`.
- Re-submitting identical content writes no row.
- Two sequential edits produce `sequence` 0 and 1; the first `before_text` is still the AI original.
- Accept with no prior edit writes no row.
- Reject with no prior edit writes no row.
- Direct user authoring writes no row.
- `supersede()` writes no row.
- **Negative/mutation test:** deleting the capture call from `edit_review_entry` must fail a test. Without this, the suite does not actually protect the feature.

**Capture — Path B**
- A continuation writes one unsettled row (`settled_at IS NULL`) whose `before_text` equals the streamed buffer exactly.
- `context.insert_offset` correctly locates the segment in the pre-append `content_text`.
- The stream error path marks `partial_stream = true`, **and** a capture failure inside that branch does not replace the provider error the author needs to see (§9.2).
- The next continuation settles the prior row exactly once and writes a new unsettled row.
- A second settle attempt is a no-op, not an error.
- An author `update_chapter()` save writes **no** capture row and settles nothing (§6.3.1).
- A chapter whose last continuation is never followed by another keeps exactly one unsettled row, and §13 still returns it with a live-resolved after-side.
- An oversize before-text on an unsettled row is representable: `before_state='oversize'`, `before_text IS NULL`, `after_state IS NULL`, `settled_at IS NULL`. **This row is the regression test for the constraint defect §8.2 corrects** — it must insert successfully.

**Transaction semantics**
- Tier 1: an induced INSERT failure rolls the edit back — the Entry content is unchanged and the API returns an error. Assert the pre-image survived.
- Tier 2: an induced failure rolls the chapter append back.
- Tier 3: an induced settle failure leaves the row unsettled, logs a warning, and returns a successful response.
- Grep-style assertion that no bare `except Exception: pass` exists around capture calls.

**Idempotency / concurrency**
- Concurrent edits of one Entry never produce duplicate `sequence` values (unique violation asserted, not swallowed).
- Replayed settle affects zero rows.
- `_append_chapter()` emits `FOR UPDATE` for the chapter row before deriving `sequence` (§10.1). Assert the lock is taken — a test that only exercises SQLite proves nothing here, because SQLite ignores the clause; assert on the compiled statement or the repository call.

**Size and privacy**
- A `> EDIT_DIFF_MAX_CHARS` side yields that side's state `= 'oversize'` with NULL text and correct hash and length, **independently of the other side's state**.
- **No truncated text is ever stored** — assert `before_text` is either the full string or NULL.
- Deleting a chapter cascades its captures away, **through the database**, with no ORM relationship nulling `chapter_id` first (§12). Assert zero rows remain, not merely zero rows with a non-null `chapter_id`.
- Deleting a user cascades all captures away.
- Soft-deleting a Work retains rows and excludes them from §13 reads.
- No captured text appears in any log record (assert against a capturing log handler).

**Non-interference**
- Full `tests/golden/*`, `test_prompt_budget.py`, `test_streaming.py` unchanged.
- Assembled prompts are byte-identical with and without captures present.
- `retrieve()` results are unaffected by capture rows.
- Regression items R6 (continuation) and R9 (lossless migration) from the milestone checklist.

**Read contract**
- `list_edit_diff_captures` is owner-scoped, excludes `oversize` / non-canon / partial / soft-deleted-work / missing-chapter rows, **includes** a trailing unsettled `chapter-continuation` row with its after-side resolved live and labelled `after_source = "live-chapter"`, and paginates deterministically.

---

## 18. Rollout and rollback

**Rollout**

1. Migration `0003_edit_diff_capture` only — no behavior change. Verify head and a clean test run.
2. Path A capture (Entry review edit). Smallest surface, sharpest data loss, no UX effect.
3. Path B draft capture (`_append_chapter`).
4. Path B settle trigger (§6.3 — next continuation; §19-Q1 is answered and needs no further decision).
5. The §13 read contract, when P2-5 begins.

Steps 2–4 are separate PRs over one migration. Splitting the migration would create three
revisions for one table.

**Feature flag? Decided: none** (§19-Q7), and this differs deliberately from P1-6. A flag that
defaults OFF on a *capture* feature means collecting nothing, which is the failure mode
ADR-010 §4-C names. A flag that defaults ON is not a flag. The divergence from P1-6 is
principled rather than inconsistent: P1-6's flag guarded a change to what reached a live
generation prompt, whereas P1-7 changes nothing the author or the model can observe.

**Rollback**

- Any step: revert the code PR. Capture stops; existing rows are inert and harm nothing.
- The migration itself: leave the table in place. An empty unused table costs nothing, and
  `downgrade()` destroys unrecoverable data (§14).
- No canon, chapter, prompt, or retrieval behavior depends on the table, so rollback cannot
  cascade.

---

## 19. Open questions — resolved

All eight are closed by the independent architecture review of 2026-08-09. Each carries one
of three dispositions: **RESOLVED** (decided here), **DEFERRED WITH SAFE DEFAULT** (a later
task owns it; a default that cannot hurt is recorded), or **BLOCKING HUMAN DECISION** (nothing
may be implemented until a person answers). **There are no BLOCKING items.**

| | Question | Disposition |
|---|---|---|
| Q1 | Path B settle trigger | **RESOLVED** — next continuation + read-time resolution |
| Q2 | `EDIT_DIFF` provenance validator | **DEFERRED WITH SAFE DEFAULT** — P2-5 owns it; P1-7 touches nothing |
| Q3 | Capture on supersession | **RESOLVED** — no capture |
| Q4 | Keep oversize rows | **RESOLVED** — keep, metadata-only |
| Q5 | ADR-010's "one column pair" | **RESOLVED** — illustrative, not binding DDL |
| Q6 | Retention ceiling | **RESOLVED** — indefinite, no automatic expiry in P1-7 |
| Q7 | Kill switch | **RESOLVED** — no feature flag |
| Q8 | Table name | **RESOLVED** — `edit_diff_captures` |

**Q1 — What settles a Path B capture? → RESOLVED.** The write-path trigger is **the next
continuation of the same chapter**, exactly as §6.3 proposed, and the trailing unsettled row
is resolved **at read time** from live `chapters.content_text` (§6.3.1, §13 rule 2). This was
the one question the design called a genuine product decision, and the review closes it
rather than escalating it, because the repository does contain the information needed to
decide: the four candidate triggers were each checked against the real editor page, the real
`PATCH /works/chapters/{id}` endpoint, and the real 1.2-second autosave, and the comparison in
§6.3.1 is decisive. The decisive facts are that (a) only the before-side is irrecoverable, so
the settle snapshot is a bracketing convenience rather than a rescue, and (b) the one
high-coverage alternative — settling on the author's own save — would systematically record
"the human changed nothing," biasing the corpus in exactly the dimension it exists to
measure. Choosing it would have been the wrong decision, not merely a different one.

**Q2 — Does `ProvenanceSourceKind.EDIT_DIFF` still fit its own validator? → DEFERRED WITH
SAFE DEFAULT.**
`EntryService._validate_provenance()` ([`entry_service.py:835`](../../backend/app/services/entry_service.py#L835))
requires an `EDIT_DIFF` provenance `source_id` to be an owned **Chapter**. But ADR-010 §2.3
describes the distilled Entry's provenance as a *"diff batch"*, and a preference distilled
from many chapters has no single chapter. The review confirmed the mismatch is real in code:
the `EDIT_DIFF` branch shares the `CHAPTER` branch's `_assert_owned_record(..., Chapter, ...)`
call, so a distilled preference with no single source chapter cannot be persisted today.
**Safe default: change nothing.** P1-7 writes no Entry at all (§5.4), so the validator is
never exercised by this feature, and any fix now would be speculation about a P2-5 output
shape nobody has designed. Recorded so P2-5 does not discover it late.

**Q3 — Is a canon supersession a learning signal? → RESOLVED: no capture.** §4.2's reasoning
holds and was re-checked against `EntryService.supersede()`: the old canon survives as a
`superseded` row linked by `superseded_by_entry_id`, so predicate (b) of §4.1 — *completing
the write makes one text unrecoverable* — is simply false. The pair is queryable forever
without a capture row, and a read-side query over the supersession chain reconstructs it
exactly. Writing a row would duplicate durable data into a table whose whole justification is
holding data that exists nowhere else. If a future pass wants this signal, it reads the
supersession chain; that requires no schema change and no decision now.

**Q4 — Keep oversize rows at all? → RESOLVED: keep them, metadata-only.** A metadata-only row
costs on the order of a hundred bytes and makes systematic loss countable; writing nothing
makes it invisible, and an invisible gap in a corpus is worse than a measured one. This
matters more under the split state columns of §8.2, where a row can now be oversize on one
side and fully stored on the other — which is genuinely useful data, not a stub.

**Q5 — Does Option 2 satisfy ADR-010 §2.2's "one column pair on the substrate"? → RESOLVED:
the phrase is illustrative, not binding DDL.** Three independent confirmations: ADR-003 §2
says of the ADR layer that it *"writes no columns, keys, or DDL — those belong to an RFC"*;
RFC-008 §5 and §7 both state that *"capture timing and the substrate that records diffs are
Defined in the Learning Capture RFC"*, explicitly deferring the substrate away from ADR-010;
and ADR-010 §2.2's own wording scopes the column pair to *"per chapter"*, which contains no
provision at all for the Entry-level Review Card correction of §2.2 Path A. Reading it as
binding DDL would therefore not merely produce a worse schema — it would **discard one of the
two capture paths entirely**. The binding decision in ADR-010 is *capture the pair from day
one*, and Option 2 honors it on both paths. No ADR-010 revision is required; if one is ever
written for other reasons, aligning the illustrative sentence is a documentation cleanup.

**Q6 — Any retention ceiling? → RESOLVED: indefinite retention, no automatic expiry in
P1-7.** ADR-010 §2.2 is explicit that this data cannot be recollected, and §5-Future-risks'
*"retention stays local and minimal"* is already satisfied by the per-row cap (§11.1), the
cascades (§12), and the owner's unconditional delete path — not by a purge. A time- or
size-based ceiling would destroy unrecoverable data on a schedule nobody has a use case for;
the §11.3 volume estimate is single-digit megabytes per year at personal scale, so no
pressure exists. Any expiry policy is a P2-5 product decision made *after* there is a
consumer, and adding one later is additive.

**Q7 — Kill switch? → RESOLVED: no feature flag.** §18's reasoning is adopted. A capture
feature behind a default-OFF flag collects nothing, which is ADR-010 §4-C's rejected
alternative reached by accident, and a default-ON flag is not a flag. The rollback story is
already sufficient: revert the code PR and capture stops, leaving inert rows that nothing
reads (§18). This is a deliberate and recorded divergence from P1-6's flag posture, and the
reason is that P1-6 changed what reached a live prompt whereas P1-7 changes nothing the
author or the model can observe.

**Q8 — Table name. → RESOLVED: `edit_diff_captures`.** It is source-neutral, which the
schema requires: one table serves both an Entry anchor and a Chapter anchor, so
`entry_edit_diffs` would misdescribe half its rows. It matches the plural snake_case of
`entries` / `chapters` / `work_characters`, and `0003_edit_diff_capture` matches the
`000N_<snake_case>` revision convention.

---

## 20. Implementation-ready acceptance criteria

The P1-7 implementation conforms only if **all** of the following hold.

**Schema and migration**
1. Exactly one new table, created by exactly one new revision `0003_*` with `down_revision = "0002_entry_store"`.
2. `0001_initial` and `0002_entry_store` are byte-unchanged.
3. No column is added to, removed from, or altered on any existing table.
4. `alembic heads` reports the new single head; the chain applies and round-trips on SQLite and compiles for PostgreSQL.
5. All constraints and indexes of §8.2 exist and are named; no partial index, no dialect-specific predicate, no raw SQL.

**Capture correctness**
6. Every §4.2 "Yes" path writes exactly one row per qualifying event; every "No" path writes none.
7. The first Path A `before_text` for an Entry is the pristine AI-proposed content, byte-exact.
8. Path B `before_text` equals the streamed provider output, byte-exact.
9. No text is ever truncated. Oversize means NULL text plus retained hash and length, decided per side.
10. `before_sha256 == after_sha256` writes no row.

**Transaction and failure**
11. Tier-1 and Tier-2 captures are in the same transaction as the write they protect; an induced failure rolls that write back and returns an error.
12. Tier-3 settle failure leaves the row unsettled, logs a structured warning, and does not fail the request.
13. No bare exception swallowing around any capture call.
14. No captured text reaches any log, trace, error response, or Bench fixture.

**Isolation**
15. No Entry is created, mutated, promoted, or blocked by capture. `status=canon` remains reachable only through Human Review.
16. Assembled prompts and `retrieve()` results are byte-identical with and without capture rows.
17. No new HTTP endpoint, DTO, or frontend change.
18. No `misc` Entry type, no new Entry type, no new knowledge table, no change to the governed vocabulary.
19. P1-6 decisions untouched; P1-8 and P1-9 untouched.

**Privacy and lifecycle**
20. User and Chapter deletion cascade captures away; Work soft-delete retains rows but excludes them from reads.
21. Every query is owner-scoped; no unscoped or cross-user read path exists.

**Corrections carried from the architecture review — implementation must satisfy these**
24. `_append_chapter()` (and the §6.3 settle path) load the chapter with `with_for_update()` before deriving `sequence` (§10.1). The in-process `_active_continue` set is not accepted as the serialization mechanism.
25. Deletion cascades are enforced by the database. No ORM `relationship()` to `edit_diff_captures` exists without `passive_deletes=True` (§12).
26. `before_state` and `after_state` are independent columns; there is no single `payload_state`, and "pending" is expressed only as `settled_at IS NULL` (§8.2).
27. An unsettled `chapter-continuation` row is a valid terminal state. Nothing treats it as an error, and the §13 read path returns it with a live-resolved after-side (§6.3.1).
28. `EDIT_DIFF_MAX_CHARS` is a code constant with no schema dependency; changing it requires no migration and does not invalidate existing rows (§11.1).

**Verification**
22. The §17 test plan passes, including the mutation checks that prove the tests detect removal of the capture calls.
23. Ruff clean; MyPy introduces no new error in the changed scope; full pytest passes with no reduction in count.

---

## 21. Why this is an implementation note, not an ADR or RFC

RFC-001 §5 names **Learning Capture** as the eighth lifecycle stage, and the dependency
tables of RFC-007 §14, RFC-008 §12, RFC-009 §14, RFC-011 §14, and RFC-012 §14 all defer to
*"the Learning Capture & Distillation RFC"* — a document that does not exist. RFC-001's RFC map lists Learning
Capture under **"Unnumbered future topics … Assign a number only when the RFC file is
created,"** and `docs/architecture/README.md` §"INFO" records it as intentionally unwritten.
So a number is available; it is not reserved.

This document deliberately does not claim it, for three reasons:

1. **It would be half an RFC.** The named RFC owns capture *and* distillation. Distillation
   is P2-5 and is explicitly out of scope here (§16). Publishing RFC-013 covering only
   capture would either freeze a distillation contract nobody has designed, or leave a
   numbered RFC permanently incomplete.
2. **No ADR-level decision is being made.** Every choice here is made *inside* the space
   ADR-003, ADR-010, ADR-011, and ADR-017 already fixed. The one place that brushes a hard
   rule — a non-knowledge table under RFC-001 §8.10 — was raised for explicit ratification in
   §5.3 rather than decided unilaterally, and the independent review ratified it on the
   ground that the valve governs knowledge promotion while ADR-015 §2.2 separately sanctions
   new tables. No ADR is therefore required.
3. **Precedent.** [`prompt-assets.md`](prompt-assets.md) (P1-3),
   [`review-card-api.md`](review-card-api.md) (P1-1), and
   [`entry-context-integration.md`](entry-context-integration.md) (P1-6) are all
   implementation notes recording equally consequential decisions.

**When this should become RFC-013 (Learning Capture & Distillation):** when P2-5 is scoped.
At that point the capture contract here becomes its §-on-capture, distillation is designed
alongside it, and the five deferring RFCs get a real cross-reference. §5.3's ratification
means no ADR is required before implementation.

---

*End of the P1-7 edit-diff capture design. The design is approved; nothing in it is
implemented.*
