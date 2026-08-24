---
description: Conventions for photo/barcode recognition and any derived nutrient estimation in food-recognition-service. Use whenever designing or reviewing anything that classifies an uploaded food photo, decodes a barcode, or estimates a nutrient value from either.
---

# Media Recognition Conventions — `food-recognition-service`

Specification for how media-recognition and any derived estimation must be
designed. This is the contract `media-recognition-agent` and
`architecture-agent` review implementation against; it does not choose a
specific model or write any inference code itself.

## Confidence Must Always Be Explicit
- Every detection (item identified, value estimated) must carry a
  confidence score, not just a label. There is no "silent" high or low
  confidence — the score is always surfaced through the port contract to
  the application layer.
- Define, per detection type, the confidence threshold below which the
  result is treated as "uncertain" rather than "detected." This threshold
  must be documented in the service's `README.md` once implemented, and
  must be tunable without a code change (config, not a magic number).

## User-Facing Behavior for Uncertain Results
- Below the confidence threshold: never auto-write a value silently.
  Present the estimate as a suggestion the user must confirm or correct
  before it is written to `diary-service`.
- If multiple candidates are plausible for the same media region, surface
  the top candidates rather than silently picking one.
- If detection fails entirely (no confident candidate), the fallback is
  always manual entry — never a guess presented as a result.

## Estimation Ranges
- If the recognition task includes any quantitative estimate (size,
  weight, count, duration, etc.), it is inherently approximate. Present it
  as a range or with an explicit margin, not a single precise number
  implying false accuracy (e.g. "approx. 150–180 units", not "163 units").
- Any calibration method used (reference objects, known scale, etc.) must
  be documented as part of the estimation method, since it affects how
  confidence is interpreted downstream.

## Model Lifecycle
- Whatever model/provider is chosen (in-house, third-party API) is a
  resilience-pattern dependency like any other external call — circuit
  breaker, timeout, retry, explicit fallback, per
  `.claude/skills/resilience-patterns/SKILL.md`. Fallback on total
  unavailability is always manual entry, never a stale/cached guess
  presented as fresh.
- Model version must be recorded alongside every detection event
  (`payload.model_version` in the domain event), so that a later change
  in model behavior can be correlated with a change in detection quality.
- Any change of model or provider is an ADR-worthy decision (see
  `CLAUDE.md` section 9), since it changes accuracy characteristics and
  potentially data-handling/privacy posture (see below).

## Data Handling & Privacy
- If the uploaded media is or could be sensitive personal data (per
  `docs/data-protection-and-privacy.md`), any third-party recognition API
  used must have its data-retention policy for submitted media reviewed
  and documented before use — the goal is to avoid a third party retaining
  or training on user media without explicit disclosure and consent.
- Media is never used to train or fine-tune a shared model without
  explicit, separate, opt-in consent from the user — this is distinct
  from consent to use the feature itself.

## Evaluation
- Maintain a fixed, versioned test media set (varied conditions relevant
  to your domain) with expected labels/values and acceptable tolerance,
  used to benchmark any model or prompt change before release.
- Track detection accuracy and confidence-calibration drift over time as
  an observability metric (per
  `.claude/skills/observability-audit/SKILL.md`), not just uptime/latency.

## Testing
- Unit tests for the domain/application layers use fixture detection
  results (mocked), never live model calls.
- Any live-model integration test is explicitly marked and excluded from
  the default CI run, run on a separate, rate-limited schedule instead —
  consistent with how `external-data-ethics/SKILL.md` treats live external
  sources.
