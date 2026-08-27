# nutrition-calculation-service — agent-scoped notes

This file is scoped guidance for any agent working inside
`services/nutrition-calculation-service/`. It does not replace the root
`/CLAUDE.md` (architecture, workflow, guardrails) or
`.claude/agents/nutrition-calculation-agent.md` (bounded context, domain
responsibilities, rules) — read both first, and read
`.claude/skills/domain-calculation-conventions/SKILL.md` before touching
any formula in `domain/services/` — it is mandatory, non-negotiable
reading.

## Quick orientation

- Hexagonal layout: `domain/` -> `application/` -> `infrastructure/`,
  dependencies point inward only (ADR-0001). The domain layer never
  imports SQLAlchemy, FastAPI, httpx, aio_pika, or redis.
- Event-driven CRUD (ADR-0002 exception) + Outbox — not event-sourced.
  Conventional upsert-by-natural-key at the storage layer, reinforced by
  consumer-level `ProcessedEventsPort` dedup (`(consumer_name, event_id)`).
- Three live inbound event dependencies (diary-service, profile-service,
  catalog-service) plus one synchronous outbound call
  (`ProfileRevealClient` -> `profile-service`). Every formula lives in
  `domain/services/*.py` as a pure function — zero framework dependencies,
  cites its source in its docstring.

## Never do this

- Never persist a plaintext `weight_kg`/`height_cm`/`age`/`sex` value
  anywhere in `user_metrics_snapshot` (or any other table). See
  `infrastructure/persistence/models.py`'s `UserMetricsSnapshotModel`
  docstring and the schema-level negative test guarding this
  (`tests/integration/infrastructure/test_postgres_user_metrics_snapshot_repository.py`).
  This is a hard, security-reviewed constraint (implementation plan
  Addendum 1, security sub-addendum requirement 8), not a style
  preference — changing it requires a new human-approved decision, not a
  quiet refactor.
- Never let `RabbitMqProfileMetricsConsumer` read or decrypt the
  ciphertext fields on `WeightRecorded`/`BodyMetricRecorded`/`GoalSet`/
  `GoalUpdated` — those events are triggers only (`user_id` + which field
  changed); plaintext metrics come exclusively from `ProfileRevealPort`.
- Never default or guess a biometric input. `Sex.OTHER` requires an
  explicit `calculation_sex_constant`; a `ProfileRevealClient` failure
  (circuit open, timeout, 404/401/403/429) must defer the recompute
  (`RecomputeNutritionTargetDeferredError`), never fall back to a stale or
  invented value.
- Never make a live HTTP call to a real `profile-service` in this
  service's own test suite — `ProfileRevealClient`'s tests use
  `httpx.MockTransport` fixtures exclusively.
- Never add micronutrient data to a total when there is no
  `nutrient_panel_mirror` match — mark it `"unavailable"` explicitly; the
  gap is an accepted, eventually-consistent trade-off (implementation
  plan section 6(b)), not something to paper over.
- Never bump `CURRENT_FORMULA_VERSION` or change the activity-factor
  table / calorie-target safety bounds without a new ADR proposal
  (`.claude/skills/domain-calculation-conventions/SKILL.md` section 1).

## Where things live

- Ports: `domain/ports/*.py` (Python `Protocol`s).
- Adapters: `infrastructure/persistence/`, `infrastructure/caching/`,
  `infrastructure/messaging/`, `infrastructure/http/profile_reveal_client.py`.
- Composition root: `infrastructure/composition_root.py` — the only place
  concrete adapters are wired to ports.
- The naming-translation anticorruption layer:
  `domain/services/nutrient_vocabulary_translator.py` — this service's own
  canonical nutrient vocabulary, translating both diary-service's and
  catalog-service's raw shapes into it (implementation plan section 6(g)).
- Tests mirror `testing-strategy` SKILL.md's layout under `tests/`.

## Coverage floors (treat domain's as a hard floor, per the agent doc)

Domain >= 90%, application >= 85%, infrastructure >= 70%. Mutation testing
(`mutmut`, domain layer only) is recommended, advisory/non-blocking in CI
(`.github/workflows/nutrition-calculation-service-ci.yml`'s
`mutation-testing` job).
