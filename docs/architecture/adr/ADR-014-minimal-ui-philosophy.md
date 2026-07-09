# ADR-014: Minimal UI Philosophy

- **Status:** Accepted — *ratifies and locks the `design.md` mobile-first, fixed-navigation, progressive-disclosure UX model*
- **Date:** 2026-07-09
- **Deciders:** Architecture Review Board
- **Related:** ADR-001, ADR-011, ADR-015

## 1. Context

The product is internally rich (multiple engines, a Bible, a flywheel) but its explicit promise is that **the end-user experience stays simple** ("내부는 고도로 모듈화되어 있으나 최종 사용자 경험은 단순함을 최우선"). `design.md` §7 already specifies a strong UX constitution: mobile-first from 360px, a fixed bottom tab bar (Home/Character/World/Novel/Chat), a **3-tap rule**, progressive disclosure of advanced options, and the invariant that **new features never change the top-level navigation** (BR-7) — they enter via feature flags, slots, tabs, drawers, or the command palette (§7.15).

The perennial risk is **feature-driven UI sprawl**: every new capability (relationship graph, playground, cost dashboard, bench, reference analysis) wants a home in the primary navigation, and the sum is an unusable, un-simple product. This ADR locks the discipline so that all the *other* ADRs' future features have nowhere to bloat the core surface.

## 2. Decision

**Adopt and lock the minimal-UI constitution as a hard constraint on all current and future work.**

1. **Fixed top-level navigation.** The primary surface (Home / Character / World / Novel / Chat) is **invariant**. No feature — including any adopted in this ADR set — may add a top-level navigation item. (Enforceable as a review rule and, ideally, a check.)
2. **3-tap rule.** Any core task is reachable within three taps from Home.
3. **Progressive disclosure.** Advanced/expert controls are hidden behind "advanced" toggles, drawers, secondary tabs, or the command palette (L2/L3), never surfaced by default. Defaults are opinionated so the common path needs no configuration.
4. **Mobile-first, installable PWA.** Layout is designed from the smallest width up; touch targets, safe areas, and offline behavior are first-class (MOB-*, A11Y-*). Desktop is an enhancement of the mobile design, not a separate design.
5. **Extensions enter only through the sanctioned mechanisms** (ADR-015): feature flag → slot/lazy route/in-screen tab/drawer/command. Flag-off means zero UI and zero bundle impact.
6. **Review Cards (ADR-011) and every AI-proposal surface obey the same rule** — they live inside existing screens and advanced affordances, never in the primary nav.

## 3. Alternatives Considered

- **A. Feature-rich dashboard UI** — expose the product's internal richness (engines, bible, analytics) as first-class navigation.
- **B. Desktop-first, responsive-down** — design for desktop, adapt to mobile.
- **C. Fully configurable/customizable UI** — let the user compose their own navigation/panels.
- **D. Grow navigation organically** — add a nav item whenever a feature seems important.

## 4. Why Rejected

- **A — Feature-rich dashboard:** Directly contradicts the product's core promise of simplicity and would bury the two things users actually do (chat, write) under machinery. The internal richness is a means, not a surface. Rejected.
- **B — Desktop-first:** The product is explicitly mobile-first (로판AI/하트픽션 lineage, PWA, MOB-* requirements). Designing for desktop and squeezing down reliably produces poor mobile ergonomics. Rejected.
- **C — Fully customizable UI:** Enormous complexity (layout engine, persistence, testing across configurations) for a single user, and it pushes design decisions onto the user. Opinionated defaults serve a personal tool far better. Rejected.
- **D — Organic nav growth:** This is the exact failure mode the constitution exists to prevent. "Just one more tab" repeated ten times destroys simplicity. The discipline must be a hard rule, not a case-by-case judgment. Rejected.

## 5. Consequences

**Positive**
- The daily experience stays calm and simple no matter how much internal capability accrues.
- Feature work is *forced* into non-invasive slots, which also keeps the code modular (flag-gated, lazy).
- Mobile-first + PWA delivers the intended "personal creative tool in your pocket" feel.

**Negative**
- Advanced features are less discoverable (behind disclosure); power users must learn where things live.
- The fixed-nav constraint occasionally makes a genuinely central new capability feel cramped fitting into an existing screen's tabs.
- Enforcing "no new top-level nav" requires ongoing discipline/review (ideally an automated check).

**Future risks**
- If the product's scope ever legitimately broadens (e.g. a distinctly new top-level activity beyond chat/novel), the five-tab lock may need a deliberate, rare revision — which should be a conscious re-decision here, not a drift.
- Over-hiding features can make them effectively invisible/unused; disclosure levels need occasional review against real usage.

## 6. Future Revisit Conditions

- Revisit the fixed top-level set **only** if a genuinely new primary activity emerges that cannot honestly live inside Home/Character/World/Novel/Chat — and then only by explicit amendment.
- If usage shows key advanced features are undiscoverable, revisit their disclosure level (promote within a screen) without adding top-level nav.
- Reassess mobile-first weighting only if the actual usage decisively shifts to desktop (unlikely for this product).
