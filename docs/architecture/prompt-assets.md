# Repository Prompt Assets

- **Status:** Implemented by Phase 1 P1-3
- **Authority:** ADR-013, ADR-009, RFC-009

## Asset root and current inventory

Architecture-owned creative prompt bodies live under `backend/prompts/`. This
location is stable relative to the backend package and is copied by the existing
backend Docker build context; lookup never depends on the process working
directory or a caller-provided absolute path.

| Asset ID | Version | File |
|---|---:|---|
| `chat.default` | `v1` | `backend/prompts/chat/default.v1.md` |
| `novel.continue` | `v1` | `backend/prompts/novel/continue.v1.md` |
| `summary.rolling` | `v1` | `backend/prompts/shared/rolling-summary.v1.md` |

The directory convention reserves `analyst/`, `writer/`, `chat/`, `checks/`,
and `shared/` as peer areas. Only the three legacy bodies above are introduced
in this phase; no Analyst or Writer assets are pre-created.

## Loader contract

`app.engines.prompt.assets.PromptAssetLoader` is the only loader boundary for
these assets. It accepts a stable, allow-listed asset identifier and optionally
an expected version. It resolves the registered relative path deterministically,
reads UTF-8 text, and returns the asset ID, version, body, and SHA-256 digest.
Unknown identifiers, missing registered files, and version mismatches raise
explicit loader errors. There is no DB lookup and no fallback prompt body.

Chat, Novel continuation, and Summary pass the resolved identity into
`AssembleInput`; `PromptEngine` records `{id, version, sha256}` under
`trace["prompt_asset"]`. The composed provider-neutral messages and their
existing runtime contracts are otherwise unchanged.

## Ownership boundary

| Category | Ownership and treatment |
|---|---|
| Architecture-owned creative body | **Repository prompt asset.** Maintainers change a diffable versioned file, test it, and commit it. The repository is the source for the asset identifier, version, body, and SHA-256 digest. |
| Runtime-generated wrapper/instruction | Runtime composition input. Current character rendering, previous-summary inclusion, labels, variable resolution, and the legacy continuation instruction remain code because their text is generated from call data or is an input default, not a standalone creative body. |
| Legacy/user-authored `PromptTemplate` | Frozen-schema compatibility data. Its user, scope, name, body, and default flag remain available through the legacy API, but its body is not an architecture-owned creative prompt source. |
| Test fixture | Test-only frozen text may duplicate a body solely to prove migration fidelity; it is not a runtime source. |

`PromptTemplate` remains an additive legacy model in the frozen `0001` schema.
Its existing `GET/POST` compatibility API preserves user-authored data,
including bodies that happen to have an asset-like name or similar text. The
allow-listed `PromptAssetLoader` has no DB lookup or fallback, and the Chat,
Novel, and rolling Summary defaults never query `PromptTemplate`; therefore DB
data cannot override a repository default.

This contract also applies to future Analyst facets, declarative Writer stages,
and Bench checks: their architecture-owned creative bodies must resolve through
repository-managed versioned assets, never `PromptTemplate.body`. P1-4 adds no
migration, schema change, data conversion, or deletion. Any future removal or
conversion of legacy `PromptTemplate` data requires separately approved work.
