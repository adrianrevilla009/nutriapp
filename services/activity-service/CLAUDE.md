# activity-service -- agent-scoped notes

This file is scoped guidance for any agent working inside
`services/activity-service/`. It does not replace the root `/CLAUDE.md`
(architecture, workflow, guardrails) or `.claude/agents/activity-agent.md`
(bounded context, domain responsibilities, rules) -- read both first.

## Quick orientation

- Hexagonal layout: `domain/` -> `application/` -> `infrastructure/`,
  dependencies point inward only (ADR-0001). The domain layer never
  imports FastAPI, SQLAlchemy, httpx, purgatory, or aio_pika --
  `FitbitProviderAdapter`'s httpx/purgatory/tenacity usage lives
  exclusively in `infrastructure/external/`.
- Event-driven CRUD (ADR-0002 exception) + Outbox -- not event-sourced.
  `exercise_entries` is a conventional, soft-deleted table, corrected in
  place.
- This MVP is **manual exercise logging**, plus a **Fitbit wearable
  adapter approved and built under the 2026-09-11 addendum** to
  `/plans/activity-service/implementation-plan.md` -- see
  `README.md`'s "Wearable sync (Fitbit)" section for current status
  (code exists, mock-tested only, feature-flag gated off, no real
  Fitbit developer account/credentials exist in this environment).
  Apple Health, Google Fit, and Garmin remain interface-only.

## Never do this

- Never add a wearable provider adapter for Apple Health, Google Fit,
  or Garmin, any OAuth flow, or a fixture simulating an unverified real
  provider API/response shape, for any provider OTHER than Fitbit.
  `domain/ports/wearable_provider_port.py` has exactly one implementation
  (`FitbitProviderAdapter`) -- adding a second provider requires its own
  real developer account and its own new, separately human-approved plan
  (`.claude/agents/activity-agent.md`'s rule: "Any change to which
  providers are supported is significant enough to warrant noting in
  `docs/vendor-risk-register.md`").
- Never remove or loosen `Container.fitbit_provider`'s feature-flag gate
  (`ACTIVITY_SERVICE_WEARABLE_SYNC_ENABLED` + non-empty client
  credentials, both required) in `infrastructure/composition_root.py`,
  and never make `FitbitProviderAdapter`'s tests hit a real Fitbit
  endpoint -- `tests/integration/infrastructure/test_fitbit_provider_adapter.py`
  is `httpx.MockTransport`-only, matching every other external-API
  adapter in this codebase.
- Never add a hard-delete path to `ExerciseRepositoryPort` or any
  concrete repository. Removal is soft delete only (`deleted_at`),
  matching `diary-service`'s convention.
- Never present `calories_burned_kcal` as more precise than its source
  claims (`.claude/agents/activity-agent.md`'s rule) -- in this MVP it is
  always the user's own estimate; do not add a silent auto-estimation
  formula without treating it as its own reviewed domain calculation
  (`.claude/skills/domain-calculation-conventions/SKILL.md`).
- Never fold the free-text `label` field (meaningful only for
  `ExerciseType.OTHER`) into `exercise_type` itself, or otherwise let it
  become a de facto second taxonomy -- it is a display-only, clearly
  secondary field in both the entity and `ExerciseLogged`'s payload.
- Never make a live call to a real wearable provider API (Fitbit
  included) or a real `nutrition-calculation-service`/`analytics-service`
  instance in this service's own test suite. `FitbitProviderAdapter` is
  the one exception to "no wearable dependency exists" -- it exists in
  code, but is tested exclusively against `httpx.MockTransport` and is
  feature-flag gated off; `nutrition-calculation-service`/
  `analytics-service` remain non-dependencies entirely. Keep it that way
  unless a new, human-approved plan changes it.

## Where things live

- Ports: `domain/ports/*.py` (Python `Protocol`s): `ExerciseRepositoryPort`,
  `OutboxRepositoryPort`, `EventPublisherPort`, `WearableProviderPort`
  (one implementation: `FitbitProviderAdapter`), `WearableTokenStorePort`
  (one implementation: `InMemoryWearableTokenStore`).
- Adapters: `infrastructure/persistence/`, `infrastructure/messaging/`,
  `infrastructure/external/` (`fitbit_provider_adapter.py`,
  `in_memory_wearable_token_store.py`).
- Composition root: `infrastructure/composition_root.py` -- the only
  place concrete adapters are wired to ports, including the
  `Container.fitbit_provider` feature-flag gate (`WearableSyncDisabledError`
  otherwise).
- Tests mirror `testing-strategy` SKILL.md's layout under `tests/`. Fake
  ports for unit tests live in `tests/fixtures/factories.py`.

## Coverage floors

Domain >= 90%, application >= 85%, infrastructure >= 70% (CLAUDE.md
section 3).
