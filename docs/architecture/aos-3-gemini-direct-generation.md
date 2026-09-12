# AOS-3 Gemini Direct Generation — implementation record

## Status and boundary

- Verification date: **2026-09-12**
- Implementation branch: `feature/aos-gemini-direct-generation`
- Base `main`: `b39e6fff48b82d8c356f241aaa1357a56c7a535b` (PR #32 merge commit)
- Status: implementation complete on the author branch; Draft PR and independent review required

AOS-3 adds no endpoint, provider-specific Novel service, prompt assembler, Scene logic,
credential store, SDK, or migration. The production path remains:

```text
ContinueRequest
→ NovelService GenerationPreparation
→ NovelEngine / PromptEngine
→ provider-neutral ProviderRequest resolution
→ existing ProviderRegistry / GeminiAdapter
→ Gemini stream as neutral text deltas
→ existing Novel token/done SSE
→ existing Chapter append + edit-diff capture
```

`ModelConfig.model_name` remains the model-selection authority. The model id below is
an implementation-time verified capability/smoke target, not a model choice embedded
in Generation Preparation, NovelService, or PromptEngine.

## Official Gemini verification

The following Google AI for Developers pages were checked on 2026-09-12:

- [Gemini 3.8 Flash model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash)
- [Gemini models and version stability](https://ai.google.dev/gemini-api/docs/models)
- [Gemini model deprecations](https://ai.google.dev/gemini-api/docs/deprecations)
- [Gemini Developer API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Using Gemini API keys](https://ai.google.dev/gemini-api/docs/api-key)
- [Generate Content API reference](https://ai.google.dev/api/generate-content)
- [Text generation and streaming](https://ai.google.dev/gemini-api/docs/generate-content/text-generation)
- [Safety settings and response feedback](https://ai.google.dev/gemini-api/docs/safety-settings)
- [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)

Practical target verified from those sources:

| Property | Verified value |
|---|---|
| Model id | `gemini-3.8-flash` |
| Status | Stable |
| Input token limit | 1,048,576 |
| Output token limit | 65,536 |
| Text output | Supported |
| Streaming | `models.streamGenerateContent`, SSE, supported |
| Standard free tier | Available; input and output listed as free of charge subject to the active project/model/tier limits |
| Authentication | API key in the `x-goog-api-key` request header; no key in URL/query |
| Shutdown | No shutdown date announced on the checked deprecation page |

The deprecation page also records the Gemini 2.0 Flash shutdown on 2026-06-01.
The practical target therefore does not use the shut-down 2.0 family or a preview
alias. Rate-limit values are not code constants: Google documents limits as varying
by model, project, usage tier, and account state, with exhausted capacity surfaced as
HTTP 429.

Google's current key documentation distinguishes standard and authorization keys,
makes new AI Studio keys authorization keys, and records the transition away from
standard keys. The repository continues to store one encrypted opaque secret string;
there is no key-type schema migration. Whichever currently accepted key the user
stores is decrypted only in backend memory by the existing call-time credential flow
and is supplied as the header value.

## Adapter and failure contract

The existing `generateContent` and `streamGenerateContent` REST paths remain in use.
The official documentation still defines both for content generation, so AOS-3 does
not migrate the provider architecture to Interactions and adds no Google SDK.

Gemini request mapping is deliberately thin:

- `AssembledPrompt.system` → `systemInstruction`, exactly once;
- non-system message order → Gemini `contents` (`user` / `model`);
- provider-neutral temperature → `generationConfig.temperature`;
- provider-neutral max tokens → `generationConfig.maxOutputTokens`.

The adapter never reads Story, Character, Relationship, Scene, or instruction domain
objects. It parses SSE framing, preserves UTF-8 text parts, selects the primary
candidate rather than concatenating alternatives, and emits plain text chunks only.

Controlled failures cover malformed/request errors, authentication/permission,
removed models, rate limiting, provider 5xx, malformed stream data, prompt/candidate
blocking, unsupported finish reasons, and empty text. Raw Google bodies and request
secrets are not included in exception messages. A first-token-free failure writes no
Chapter content, version, or edit-diff row; an existing mid-stream partial contract
remains unchanged. Registry retry remains bounded before the first token and never
restarts after streaming begins.

## Capability policy

The verified exact-model capability authority is kept in one adapter table. It
contains the current stable text-output ids checked in the official model catalog:
Gemini 3.8/3.7/3.6/3.5 Flash, 3.5/3.1 Flash-Lite, and 2.5 Flash/Flash-Lite/Pro.
Their model pages report 1,048,576 input and 65,536 output tokens. Unknown future
model ids are not guessed as 1M-context models; they receive the conservative 32,768
input / 8,192 output fallback. Provider-neutral ModelConfig creation rejects an
output reservation above the reported maximum, while call-time resolution clamps an
older persisted row to the capability before prompt budgeting. No independent clamp
exists inside Gemini request mapping.

## Test/network policy

Gemini adapter and AOS-3 integration tests use `httpx.MockTransport`; no credential is
required. The test harness blocks httpx's real sync and async network transports so a
missing fake/transport fails closed. Live Gemini smoke is opt-in only and is not part
of CI.

Final guarded automated verification made **zero** external provider/network
attempts. During an earlier author run, before that fail-closed guard was installed,
four pytest processes accidentally shared the repository's fixed temporary SQLite
database. Cross-process default-configuration contamination caused six failed
external attempts (three Gemini HTTP 400 responses using the fake
`owner-gemini-secret` test sentinel and three OpenAI HTTP 401 responses using empty or
test configuration). No production credential or protected database was read or
changed. All subsequent verification was single-process or explicitly scoped and ran
under the fail-closed transport guard. This historical incident is retained here so
the author run is not represented as having been network-free.
