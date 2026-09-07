# analytics-service -- agent-scoped notes

This file is scoped guidance for any agent working inside
`services/analytics-service/`. It does not replace the root `/CLAUDE.md`
(architecture, workflow, guardrails) or `.claude/agents/analytics-agent.md`
(bounded context, domain responsibilities, rules) -- read both first,
plus `.claude/skills/cqrs-event-sourcing/SKILL.md`,
`.claude/skills/messaging-conventions/SKILL.md`, and
`.claude/skills/resilience-patterns/SKILL.md` before touching any of the
four message consumers or `application/entitlement_check.py`.

## Quick orientation

- Hexagonal layout: `domain/` -> `application/` -> `infrastructure/`,
  dependencies point inward only (ADR-0001). The domain layer never
  imports FastAPI, SQLAlchemy, httpx, aio_pika, or pydantic.
- **CQRS, read side only** (ADR-0002's addendum) -- there is no
  event-sourced or conventional write aggregate here. Every table this
  service owns is a read projection fed by consuming another service's
  events, except `outbox`/`export_audit_log`/`anomaly_alerts` (this
  service's own bookkeeping).
- Trend/statistical logic (`domain/services/trend_calculator.py`,
  `domain/services/anomaly_detector.py`) is pure functions: no I/O, no
  repository access, takes already-fetched/windowed data in.
- `domain/tracked_nutrients.py` documents a real, live gap: only
  `protein_g`/`fat_g` have real target data flowing through the
  deficiency-detection mechanism today (`NutritionTargetUpdated` has no
  micronutrient `target_min` field in its actual schema). Do not silently
  "fix" this by inventing target data -- extending it requires a
  `nutrition-calculation-service` schema change, out of scope here.
- `food_entry_contributions`/`water_intake_contributions`/
  `micronutrient_current_targets` are internal ledger tables, not in the
  original implementation plan's table list -- added because
  `FoodEntryDeleted`/`WaterIntakeRemoved` carry no amount to reverse
  (see `domain/ports/daily_log_summary_repository_port.py`'s docstring).

## Never do this

- Never write a fallback `EntitlementCheckPort` result back into
  `entitlement_cache` -- `application/entitlement_check.py`'s
  `is_user_entitled` has no reference to the cache repository's write
  method at all; keep it that way.
- Never add an entitlement-port parameter to `GetWeeklyTrendHandler`'s
  constructor -- trends are NOT Pro-gated (structurally guarded, see
  `tests/unit/application/test_get_weekly_trend.py`).
- Never add a `FollowRepositoryPort`-style destructive dependency to
  `HandleEntitlementRevokedHandler` -- revocation only ever flips the
  cached flag.
- Never retroactively rewrite an already-persisted `micronutrient_window`
  row's `target_min` when `NutritionTargetUpdated` changes the current
  target -- only `micronutrient_current_targets` (a separate table)
  changes; historical rows keep the target that was in effect when
  written.
- Never skip the `export_audit_log` write on a successful report/export --
  every call logs, this is not idempotency-deduplicated like event
  consumption.
- Never make a live call to a real `billing-service` instance in this
  service's own test suite -- `httpx.MockTransport` fixtures only.

## Where things live

- Ports: `domain/ports/*.py` (Python `Protocol`s).
- Adapters: `infrastructure/external/billing_entitlement_client.py`,
  `infrastructure/persistence/` (eleven Postgres repositories),
  `infrastructure/messaging/` (four topic consumers sharing
  `resilient_topic_consumer.py`'s retry/DLQ plumbing, plus
  `RabbitMqEventPublisher`, `OutboxRelayWorker`).
- Composition root: `infrastructure/composition_root.py`.
- Shared cross-handler helper (not a port, not a command):
  `application/entitlement_check.py`,
  `application/detect_nutrient_deficiency.py` (cooldown + publish logic
  called by `HandleNutritionValueRecomputedHandler`).
- Tests mirror `testing-strategy` SKILL.md's layout under `tests/`. Fake
  ports for unit tests live in `tests/fixtures/factories.py`.

## Coverage floors

Domain >= 90%, application >= 85%, infrastructure >= 70% (CLAUDE.md
section 3). Actual as of 2026-09-07: 99% / 98% / 85%.
