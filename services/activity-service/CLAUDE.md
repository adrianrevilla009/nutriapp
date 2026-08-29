# activity-service -- agent-scoped notes

This file is scoped guidance for any agent working inside
`services/activity-service/`. It does not replace the root `/CLAUDE.md`
(architecture, workflow, guardrails) or `.claude/agents/activity-agent.md`
(bounded context, domain responsibilities, rules) -- read both first.

## Quick orientation

- Hexagonal layout: `domain/` -> `application/` -> `infrastructure/`,
  dependencies point inward only (ADR-0001). The domain layer never
  imports FastAPI, SQLAlchemy, or aio_pika.
- Event-driven CRUD (ADR-0002 exception) + Outbox -- not event-sourced.
  `exercise_entries` is a conventional, soft-deleted table, corrected in
  place.
- This MVP is **manual exercise logging only**
  (`/plans/activity-service/implementation-plan.md` section 1) -- no real
  OAuth developer-account credentials exist for any wearable provider.

## Never do this

- Never add a wearable provider adapter (Apple Health, Google Fit,
  Fitbit, Garmin), any OAuth flow, or a fixture simulating an unverified
  real provider API/response shape. `domain/ports/wearable_provider_port.py`
  is interface-only, deliberately zero implementations, until a real
  developer account exists for a given provider and a new, separately
  human-approved plan authorizes building against it.
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
- Never make a live call to a real wearable provider API or a real
  `nutrition-calculation-service`/`analytics-service` instance in this
  service's own test suite -- none exist as dependencies of this service
  today; keep it that way unless a new, human-approved plan changes it.

## Where things live

- Ports: `domain/ports/*.py` (Python `Protocol`s): `ExerciseRepositoryPort`,
  `OutboxRepositoryPort`, `EventPublisherPort`, `WearableProviderPort`
  (zero adapters).
- Adapters: `infrastructure/persistence/`, `infrastructure/messaging/`.
- Composition root: `infrastructure/composition_root.py` -- the only
  place concrete adapters are wired to ports.
- Tests mirror `testing-strategy` SKILL.md's layout under `tests/`. Fake
  ports for unit tests live in `tests/fixtures/factories.py`.

## Coverage floors

Domain >= 90%, application >= 85%, infrastructure >= 70% (CLAUDE.md
section 3).
