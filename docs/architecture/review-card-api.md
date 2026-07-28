# Entry Review Card API — Phase 1 implementation note

This note records the deliberately small backend boundary that operationalizes
RFC-001, RFC-002, and RFC-011 without defining or implementing Review Card UI.

## Phase 1 boundary

All endpoints are authenticated and derive `user_id` from the existing current-user
dependency. Request bodies cannot select an owner or lifecycle status.

- `GET /api/v1/entries/review` lists the current owner's `proposed` Entries.
- `GET /api/v1/entries/review/{entry_id}` reads one owned `proposed` Entry.
- `POST /api/v1/entries/review/{entry_id}/accept` applies the existing
  `proposed -> canon` transition after rechecking owned, live scope, subject, and
  persisted internal provenance anchors.
- `POST /api/v1/entries/review/{entry_id}/reject` applies only the
  `proposed -> rejected` transition.
- `POST /api/v1/entries/review/{entry_id}/edit` changes only `title`, `content`,
  and `data` while leaving the Entry `proposed`. The service records the
  provenance capture method as `human-edited`.
- `POST /api/v1/entries/review/{entry_id}/supersede` promotes the proposed
  Entry named by the path as the replacement for the owned canon named by the
  request body's `current_entry_id`.

The supersede request is exactly:

```json
{"current_entry_id":"<owned-canon-entry-id>"}
```

Unknown fields are rejected. In particular, callers cannot supply `user_id`,
`owner`, or a lifecycle status. The authenticated current user decides ownership.
The response is:

```json
{"old_entry":{"status":"superseded"},"new_entry":{"status":"canon"}}
```

Both values are complete `EntryRead` objects, including identity, type, status,
scope, subject, content, provenance, confidence, priority, lifecycle timestamps,
and ordinary created/updated timestamps. Owner-invisible Entries use the existing
not-found behavior. Repeated or otherwise non-proposed accept, reject, edit, or
detail actions return an explicit lifecycle validation error rather than silent
success.

## Accept versus supersede

Use **Accept** only when a proposal has no current canon with its identity. It
performs the ordinary `proposed -> canon` transition. Existing single-current
entries reject that transition when a matching canon already exists.

Use **supersede** only when a human reviewer has an owned proposed replacement
and an owned current canon for the same identity. It reuses
`EntryService.supersede()` and commits one atomic lifecycle change:

```text
old current: canon    -> superseded
replacement: proposed -> canon
```

The operation locks the active owner and both owner-scoped Entries, checks both
statuses, rejects self-replacement and prior replacements, verifies acyclicity,
and commits only after all checks pass. Therefore no committed intermediate state
with zero or two current Entries is externally observable.

Supersession preserves the existing identity and single-current rules. The old
and new Entries must match in owner, scope kind/id, governed type, subject
kind/id, and subject data. This keeps `relationship.state` tied to its normalized
canonical character-pair identity and `story.summary` tied to its work/chapter
identity. `relationship.state` and `story.summary` therefore retain exactly one
current canon for each identity. Incompatible identities return a validation error.

Before promotion, the replacement runs the same persisted-anchor validation as
Accept. Missing, owner-invisible, soft-deleted, or invalid scope/subject anchors;
invalid or owner-invisible provenance anchors; and invalid or owner-invisible
chapter-origin anchors all reject supersession. The route cannot be an AI direct-to-canon bypass: producers still create
`proposed` Entries, and only an authenticated Human Review action can promote a
replacement to canon.

## Preserved invariants

- There is no API that accepts `status=canon` or lets an AI producer write canon
  directly.
- A proposed Entry whose persisted scope/subject anchor, internal provenance
  source, or chapter-origin anchor is missing, owner-invisible, or soft-deleted
  cannot be accepted or superseded into canon.
- No migration, Entry table/schema change, retrieval ranking change, Context
  Assembly change, Analyst, Writer, Bench extension, frontend, or UI is included.

## Intentional deferrals

The current Entry persistence shape can record `human-edited` provenance and the
ordinary `updated_at`/accept/reject/supersede timestamps, but it has no dedicated
review-event or actor field. Persisting an explicit review actor, action history,
edit diff, and reversal metadata remains an open audit-contract decision and
requires a separately approved persistence design; this minimum API does not
invent an unversioned JSON audit schema.
