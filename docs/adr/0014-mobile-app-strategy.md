# ADR-0014: Mobile App Strategy

## Status
Accepted

## Date
2026-08-23

## Context
Whether the product (README.md, CLAUDE.md section 1) is mobile-first
(the core action, media capture, and reminders being mobile-native
behaviors) is a product decision this ADR does not make. The current
architecture specifies only a web frontend (React + Next.js,
`docs/frontend-architecture.md`). Whether a native mobile app is in scope
changes several already-specified decisions: push notification delivery
(ADR-0011 already anticipates this via SNS fan-out to APNs/FCM), the
`food-recognition-service` capture UX (if applicable), and
`packages/shared-contracts` (would need to serve a third client, not two).

## Decision
**No native app for v1.** A responsive, PWA-capable Next.js web frontend
(already specified in `docs/frontend-architecture.md`) is the whole
answer for v1 — no additional service, agent, or skill is created now.

**Native app remains an explicit future option, not committed.** If
pursued later, **React Native** is the recommendation over Flutter or two
separate native codebases:
- Reuses TypeScript/Zod contracts from `packages/shared-contracts`
  (`docs/monorepo-tooling.md`) directly, rather than duplicating type
  definitions in Dart or Swift/Kotlin.
- Reuses a meaningful share of business/state logic (TanStack Query hooks,
  validation) with the Next.js frontend, reducing the surface two
  independent frontend codebases would otherwise duplicate.
- A dedicated `mobile-agent` and `.claude/skills/mobile-conventions/SKILL.md`
  would be added at that point, following the same pattern as every other
  domain in CLAUDE.md section 5 — not created speculatively now.

**Revisit trigger**: sustained active usage that justifies the
investment, or concrete user feedback that photo-capture/barcode-scanning
UX on mobile web (the two flows most native-camera-dependent — see
`food-recognition-service`) is a real adoption blocker. Revisiting before
either signal exists would be exactly the premature over-engineering this
repo's general bias (ADR-0012's pattern) argues against.

## Considered Alternatives
- **Flutter** — strong single-codebase cross-platform story and good
  performance, but no code/type sharing with the existing
  TypeScript/Zod/Next.js stack; would mean maintaining validation and
  contract types twice (Dart + TypeScript).
- **Separate native (Swift/Kotlin)** — best possible platform-native UX,
  but doubles engineering surface for a project currently sized around a
  single team/agent-assisted workflow; likely disproportionate before
  product-market fit is established.
- **PWA only, no native app** — lowest cost, ships fastest, but weaker
  camera/media-capture UX for `food-recognition-service` and no reliable push
  notification delivery on iOS Safari (a real constraint for the reminder
  feature in ADR-0011). Reasonable if photo-based logging and push
  reminders are not core to the initial launch.

## Consequences
### Positive
- Ships fastest — one frontend codebase, no app-store review cycle
  gating releases.
- Camera/media-capture UX for `food-recognition-service` and push
  notification delivery on iOS Safari are real weaknesses of PWA-only —
  accepted as a known trade-off for v1, not an oversight.

### Negative / Trade-offs
- Weaker camera/media-capture UX for photo-based food logging and no
  reliable push notification delivery on iOS Safari — a real constraint
  for the reminder feature in ADR-0011, mitigated by Android push working
  normally and iOS users still able to open the app to log/check reminders.

### Follow-up actions (only if the revisit trigger above fires)
- Add `mobile-agent` to CLAUDE.md section 5 and `.claude/agents/`.
- Add `.claude/skills/mobile-conventions/SKILL.md`.
- Add an app-store release stage to `docs/ci-cd-strategy.md` and
  `docs/environments-and-promotion.md`.
- Add a mobile section to `docs/testing-strategy.md`.

## References
- `docs/frontend-architecture.md`
- `docs/monorepo-tooling.md`
- ADR-0011
