# ADR-016: Provider Adapter & Vendor Neutrality

- **Status:** Accepted (unchanged in v2 — **validated as substrate**)
- **Date:** 2026-07-09 (v1) · re-confirmed 2026-07-09 (v2)
- **Deciders:** Architecture Review Board
- **Related:** ADR-001, ADR-009, ADR-015

> **v2 note.** Both Fable reviews list provider adapters in the **substrate to keep as-is** (`architecture-final-minimal.md` §1). No change; the decision below stands verbatim.

## 1. Context

"No Vendor Lock-in" is a founding principle: the user must be able to switch LLM providers (OpenAI, Anthropic, Gemini, DeepSeek, Qwen, Ollama, OpenRouter) at runtime with no code change, and run fully offline via Ollama (NFR-8). `design.md` §13 specifies a neutral `LLMProvider` interface with per-provider adapters that normalize each provider's streaming wire format into a neutral token-delta stream, plus capability metadata, retry/backoff, and optional fallback chains.

The decision to ratify is straightforward (it directly serves a founding requirement), but the *boundaries* need locking so provider quirks don't leak into the rest of the system.

## 2. Decision

**Adopt a thin Provider Adapter layer exposing a single neutral `LLMProvider` Protocol; all provider-specific behavior is confined to adapters.**

1. **Neutral interface.** Engines and Services depend only on the `LLMProvider` Protocol (chat/stream + capability query). The Prompt Engine emits provider-neutral `messages[]` (ADR-009); the adapter renders provider-specific shape (system-message handling, tokenization quirks).
2. **Runtime swap via `ModelConfig`.** Switching provider/model is data (a `ModelConfig` change), never a code change (AC-AI-2). A registry maps provider type → adapter.
3. **Stream normalization.** Each adapter normalizes its wire format to the neutral `StreamEvent` token/done/error protocol (`design.md` §6.4/§13.6).
4. **Resilience at the adapter edge.** Transient errors (429/5xx/timeout) get exponential backoff *before stream start*; optional fallback chains are adapter/registry concerns, not engine concerns (AC-AI-4).
5. **Capability-aware.** Adapters expose model capabilities (context window, tokenizer availability); the Prompt Engine's budget uses them, with approximate counting + safety margin where no exact tokenizer exists (AC-PROMPT-6).
6. **Adding a provider = registering an adapter** (ADR-015 seam), zero core change.
7. **Image generation reuses the pattern** via a separate `ImageProvider` seam (deferred implementation — ADR-015).

## 3. Alternatives Considered

- **A. Direct provider SDK calls** scattered in engines/services.
- **B. Single provider, hard-coded** (e.g. OpenAI only), add others later.
- **C. Third-party multi-provider gateway library** as the abstraction.
- **D. Route everything through OpenRouter** and treat that as the neutrality layer.

## 4. Why Rejected

- **A — Direct SDK calls:** Couples the whole codebase to provider SDKs, makes swapping a code change, and leaks wire quirks everywhere. Destroys the founding neutrality principle. Rejected.
- **B — Single hard-coded provider:** Violates No-Vendor-Lock-in and the offline (Ollama) requirement from day one; retrofitting neutrality later is costly. Rejected — neutrality is a known-volatile boundary that warrants the seam now (ADR-015).
- **C — Third-party gateway library:** Trades provider lock-in for library lock-in and inherits its release cadence and abstractions. A thin first-party adapter set is small and fully under our control. Rejected (though an OpenAI-compatible base URL is still usable *through* our adapter).
- **D — OpenRouter as the neutrality layer:** Introduces a mandatory third-party dependency and cost, and breaks offline/local operation. OpenRouter is a fine *provider option*, not the abstraction. Rejected as the layer.

## 5. Consequences

**Positive**
- True runtime provider freedom, including fully-offline local models; directly delivers a headline value proposition.
- Provider quirks are quarantined in thin adapters; the rest of the system stays clean and testable against a fake adapter.
- New providers are cheap to add.

**Negative**
- Normalizing heterogeneous streaming formats and error semantics is real, ongoing work; each provider has edge cases.
- Token counting without a provider tokenizer is approximate, slightly wasting budget (accepted trade, ADR-009).
- Capability metadata must be maintained as providers release new models.

**Future risks**
- Providers may expose features that resist neutral expression (tool calls, structured output, prompt-caching APIs); the neutral contract may need careful extension (coordinate with ADR-009 §6).
- Fallback chains can mask a misconfigured primary provider; observability is needed.

## 6. Future Revisit Conditions

- Revisit the neutral contract if a widely-used provider capability can't be expressed neutrally and matters to the product.
- Build the `ImageProvider` implementation when image generation is actually scheduled (ADR-015 trigger).
- Reassess retry/fallback policy if real usage shows it hiding failures or adding surprising cost.
