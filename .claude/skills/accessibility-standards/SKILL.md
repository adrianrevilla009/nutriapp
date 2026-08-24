---
description: Minimum accessibility (a11y) requirements for the frontend. Use whenever building or reviewing any user-facing UI component or screen.
---

# Accessibility Standards

## Target
- **WCAG 2.1 Level AA** is the minimum bar for every user-facing screen,
  not an aspirational target reviewed only at the end. Level AAA is
  encouraged where it does not conflict with core usability, but AA is
  the release gate.

## Non-negotiable Baseline
- Every interactive element (buttons, form inputs, custom components) is
  reachable and operable via keyboard alone, with a visible focus
  indicator at every step.
- Every image, icon-only button, and chart conveying information has a
  meaningful text alternative (`alt` text, `aria-label`, or an
  accessible data-table equivalent for charts) — decorative elements are
  explicitly marked as such (`alt=""` / `aria-hidden`) so they are
  correctly skipped.
- Color is never the only channel conveying meaning (e.g. an anomaly/alert
  indicator must not rely on red-vs-green alone; pair with an icon or text
  label) — this also covers color-blindness, which is common enough to
  treat as a default case, not an edge case.
- Minimum contrast ratios per WCAG AA (4.5:1 normal text, 3:1 large text
  and UI components) are enforced as part of the design system, not
  checked ad hoc per screen.
- Form inputs have programmatically associated labels (not placeholder
  text used as a label substitute) and clear, specific error messages
  tied to the field they describe.

## Domain-Specific Considerations
- Data-dense views (macro/micronutrient breakdowns, evolution graphs, the
  anomaly dashboard in `analytics-service`'s frontend) must have a
  non-visual equivalent (accessible data table or textual summary) — a
  chart alone is not an accessible way to convey an important number.
- The photo/barcode recognition flow (`food-recognition-service`) must
  have a fully usable manual-entry alternative (search-and-select from
  `catalog-service`) that does not assume the user can review or capture
  the photo visually.

## Testing
- Automated accessibility linting (e.g. axe-core or equivalent) runs in
  CI against key screens; violations at the "critical"/"serious" level
  block merge, consistent with the CI gating philosophy in
  `docs/ci-cd-strategy.md`.
- At least the critical user journeys defined in CLAUDE.md section 3
  (register -> log a food item -> see totals; photo -> AI detection ->
  logged entry; upgrade to Pro -> publish a recipe -> found in search) are
  covered by a manual or automated keyboard-only and screen-reader smoke
  pass before a release that touches those flows.

## Documentation
- Any deliberate, justified deviation from AA on a specific component
  (rare, and must have a real constraint behind it) is documented inline
  in that component and referenced from an ADR if it is a structural
  decision rather than a one-off exception.
