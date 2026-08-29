# Implementation Plan — `activity-service`

**Status:** Approved
**Date approved:** 2026-08-29
**Stage:** 2 (Implementation Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Related:** ADR-0001 (hexagonal architecture), ADR-0002 (CQRS/ES scope — event-driven CRUD), ADR-0004 (messaging backbone), `.claude/agents/activity-agent.md`, `.claude/skills/messaging-conventions/SKILL.md`, `.claude/skills/database-migrations/SKILL.md`, `docs/events-catalog.md`, `docs/api-catalog.md`, `docs/domain-glossary-and-context-map.md`, `docs/vendor-risk-register.md`

## 1. Scope

Build `activity-service` end-to-end: domain → application → infrastructure → tests, plus its Terraform/Helm/CI wiring, reusing shared platform scaffolding.

**Bounded context** (CLAUDE.md §2.2, `.claude/agents/activity-agent.md`): manual exercise logging and (in a future addition, not this plan) syncing exercise/calorie-burn data from third-party wearable providers.

**MVP scope decision (explicit human direction, this session):** with no real OAuth developer-account credentials registered for any wearable provider (Apple Health, Google Fit, Fitbit, Garmin), this plan builds **manual exercise logging only** — real, working, fully tested. The `WearableProviderPort` interface is defined in the domain layer (so the shape is settled and future adapters slot in without touching domain/application code), but **zero provider adapters are implemented** — no fixtures simulating an unverified real API contract. All four providers are explicitly documented as "not implemented, pending developer account registration," not silently absent.

**Architecture review (this session, `architecture-agent`, before this plan was written):**
- Confirmed event-driven CRUD (ADR-0002) — manual exercise entries are simple mutable state (log/edit/delete), not an append-only history where replay/audit is core product value; scoping to manual-only strengthens this classification rather than weakening it.
- Confirmed `ExerciseLogged`'s TDEE-adjustment consumption in `nutrition-calculation-service` is **deferred**, publish-only for now: `docs/events-catalog.md`'s `NutritionTargetUpdated` entry already documents `activity_adjustment_kcal` as "always `null` this pass (reserved seam for activity-service)" — the producer side deliberately left this unimplemented. Wiring a real consumer today means reopening the already-merged, already-closed `nutrition-calculation-service` (PR #6) to populate that field and touch `calorie_target_calculator.py`'s formula surface, which its own `CLAUDE.md` explicitly gates behind a new ADR. Same deferral shape as `NutrientDeficiencyDetected`/`analytics-service`.

**Acceptance criteria:**

1. **`POST /api/v1/activity/exercises`** — log a manual exercise entry: exercise type (free-text or a small closed enum — see §9), duration (minutes), calories burned (either user-estimated or left blank for a simple duration×MET-style estimate — see §9 open question), occurred-at timestamp. Publishes `ExerciseLogged` (v1) via Outbox.
2. **`PATCH /api/v1/activity/exercises/{entry_id}`** — correct a previously logged entry (never a destructive update to history beyond the entry's own current fields — this is conventional CRUD, not event-sourced, so a straightforward field update is correct here, unlike `diary-service`'s append-only correction pattern).
3. **`DELETE /api/v1/activity/exercises/{entry_id}`** — remove a logged entry (soft delete / tombstone row, matching `diary-service`'s "never a destructive row delete" convention even though this service isn't event-sourced, for the same audit-friendliness reason).
4. **`GET /api/v1/activity/exercises?date={date}`** — list the authenticated user's exercise entries for a given date.
5. **`WearableProviderPort`** defined (`connect`, `sync`, `disconnect` — the minimal shape implied by `activity-agent.md`'s domain responsibilities), zero implementations. `WearableActivitySynced` (v1) documented in `docs/events-catalog.md` as a planned, not-yet-existing event (same convention as `NutrientDeficiencyDetected`).
6. **`ExerciseLogged` (v1)** documented as Active/producer=`activity-service` in `docs/events-catalog.md`, consumers `nutrition-calculation-service`/`analytics-service` both marked "documented, not yet consuming" (mirroring the exact wording pattern already used for other pre-existing-but-unconsumed events in that file).
7. Coverage: domain ≥ 90%, application ≥ 85%, infrastructure ≥ 70% (CLAUDE.md §3).
8. `activity-service/README.md`'s "Known limitations" section (mirroring `nutrition-calculation-service/README.md`'s precedent) explicitly states: no wearable provider is implemented yet (pending developer account registration, tracked in `docs/vendor-risk-register.md`), and `ExerciseLogged` has no real consumer yet (TDEE adjustment remains a documented future addition to `nutrition-calculation-service`, out of this plan's scope).

**Explicitly out of scope for this plan:**
- All four wearable provider adapters and their OAuth flows.
- Any change to `nutrition-calculation-service` (already merged/closed) — TDEE adjustment consumption is a future, separately-planned addition.
- Deduplication logic between manual and wearable-synced entries (`activity-agent.md`'s "never double-count" rule) — not reachable without a wearable adapter to dedupe against; tracked as part of the future wearable-integration work, not this plan.
- Any `analytics-service` consumption of `ExerciseLogged` (that service doesn't exist yet, Phase 2 not yet reached in build order).

## 2. Architectural classification

**Event-driven CRUD** (ADR-0002, confirmed by architecture-agent) — not event-sourced. `ExerciseEntry` is stored conventionally (one row per entry, soft-deleted on removal), `ExerciseLogged` published via Outbox after create/update/delete, mirroring `catalog-service`'s and `food-recognition-service`'s pattern.

## 3. Files to create or modify

```
services/activity-service/
  pyproject.toml, uv.lock, Dockerfile, .dockerignore, README.md, CLAUDE.md
  alembic.ini
  migrations/versions/0001_create_activity_tables.py
      # exercise_entries (entry_id, user_id, exercise_type, duration_minutes,
      #   calories_burned_kcal, occurred_at, created_at, updated_at,
      #   deleted_at nullable -- soft delete)
      # outbox
  domain/
    entities/            # ExerciseEntry
    value_objects/         # ExerciseType (small closed enum -- see §9),
                          # DurationMinutes (positive, validated),
                          # CaloriesBurned (non-negative, validated)
    events/                # base.py (own copy, per CLAUDE.md 2.5), exercise_logged.py
    ports/                  # exercise_repository_port.py, outbox_repository_port.py,
                          # wearable_provider_port.py (interface only, zero
                          # implementations -- connect/sync/disconnect)
  application/
    commands/               # log_exercise.py, update_exercise.py, delete_exercise.py
    queries/                 # list_exercises_for_date.py
    dto/
    errors.py
  infrastructure/
    http/
      routes/                # exercise_routes.py, health.py
      schemas/
      dependencies.py         # reuses packages/shared-contracts' centralized
                          # JWT auth dependency, per established precedent
      error_mapping.py
    persistence/
      models.py, postgres_exercise_repository.py, postgres_outbox_repository.py
    messaging/
      rabbitmq_event_publisher.py, outbox_relay_worker.py
    composition_root.py, main.py
  tests/
    unit/domain/            # ExerciseType/DurationMinutes/CaloriesBurned
                          # value object validation
    unit/application/        # command/query handlers, mocked ports
    integration/infrastructure/  # testcontainers Postgres/RabbitMQ, repository
                          # round-trips, outbox relay, migration
    contract/http/         # exercise CRUD endpoints, ExerciseLogged payload
                          # contract

infra/terraform/environments/dev/activity-service.tf   # mirrors
    catalog-service.tf's structure (conventional persistence, own RDS
    schema/user, ECR repo)
infra/k8s/charts/activity-service/     # own chart, correct env-list format +
    envFrom wiring from the start (same bar every service since
    notification-service has set)
.github/workflows/activity-service-ci.yml   # mirrors the other services'
    pipelines, pinned uv/action SHAs per existing convention

docs/events-catalog.md     # ExerciseLogged: Active/producer=activity-service,
    consumers documented-not-yet-consuming; WearableActivitySynced: planned,
    not yet existing (matches NutrientDeficiencyDetected's convention)
docs/api-catalog.md        # add the four new public routes
docs/domain-glossary-and-context-map.md   # add activity-service's
    relationship entries (Open Host Service, no synchronous calls in
    either direction for this MVP)
docs/vendor-risk-register.md   # add a row (or a "not yet integrated,
    tracked" note) for each of the four wearable providers, since
    activity-agent.md explicitly requires this file be updated whenever
    provider support changes -- even "not yet supported, tracked" is
    worth recording so it isn't rediscovered from scratch later
ARCHITECTURE.md            # verify activity-service's placeholder (if any)
    is still accurate
docker-compose.yml         # add an activity-service block (own DB,
    matching catalog-service's/diary-service's pattern)
```

## 4. Ports/adapters affected

**New ports:** `ExerciseRepositoryPort`, `OutboxRepositoryPort` (Postgres adapters), `WearableProviderPort` (**zero adapters this plan** — interface only, so a future provider integration has a settled contract to implement against without touching domain/application code). No existing port from another service is reused; `packages/shared-contracts`' centralized JWT auth dependency is reused for the new routes, per established precedent.

## 5. Domain events

**Published:** `ExerciseLogged` (v1) — new entry to `docs/events-catalog.md`, `Active`, consumers `nutrition-calculation-service`/`analytics-service` both marked documented-not-yet-consuming (§1/§6).

**Documented but not implemented:** `WearableActivitySynced` (v1) — added to `docs/events-catalog.md` as planned/not-yet-existing, since no adapter publishes it in this plan.

**Consumed:** none — this service has no inbound event dependency in this MVP.

## 6. Cross-service impact

**Flagged for `architecture-agent` review, already addressed this session:** the one real cross-service question (does `nutrition-calculation-service` need a new consumer for TDEE adjustment) was resolved as **deferred** — no code change to any other service. `docs/events-catalog.md`'s consumer-list entries for `ExerciseLogged` are metadata-only (documenting a future contract), same as `NutrientDeficiencyDetected`'s existing treatment.

No other service's code, contract, or behavior changes as a result of this plan.

## 7. Resilience/caching/migration needs

- **No synchronous inter-service call in this MVP** — no circuit breaker/retry/timeout needed for this plan's scope (a future wearable adapter would need its own, per `resilience-patterns/SKILL.md`, when that work is planned).
- **No caching layer needed** — a per-user, per-date exercise list is a light, infrequent read; not a candidate for Redis at this scale, consistent with `bff-service`'s and `notification-service`'s reasoning for what does/doesn't get cached.
- **Migration**: one initial Alembic migration creating `exercise_entries` + `outbox`, purely additive (new service).

## 8. Test plan reference

`/test-plan` will define concrete test cases next: value object validation, command/query handler cases (create/update/delete/list, including the soft-delete-excludes-from-list case), repository round-trips, outbox/idempotent-publish behavior, and contract tests for the four routes and `ExerciseLogged`'s payload shape. Not enumerated further here.

## 9. Risks and open questions

1. **Exercise type: free-text or closed enum?** `activity-agent.md` doesn't specify. This plan uses a **small closed enum** (`running`, `walking`, `cycling`, `strength_training`, `swimming`, `other`) rather than free text, matching the pattern of other domain value objects in this codebase (e.g. `NotificationCategory`) being closed sets rather than unvalidated strings — easier to aggregate/analyze later (`analytics-service`) and avoids inconsistent free-text data from day one. `other` covers anything not enumerated, with an optional free-text label field for display only (never used for aggregation).
2. **Calorie estimation when the user doesn't provide a value**: this plan requires the user to supply `calories_burned_kcal` explicitly (no auto-estimation formula) — the alternative (a duration×MET-coefficient estimate per exercise type) is a real computation `nutrition-calculation-agent.md`/`domain-calculation-conventions` would want documented and tested as a domain calculation in its own right, not a five-minute addition to this plan. Deferred as a documented future enhancement in `README.md`, not built here. A required field keeps the MVP's data honest (no invented precision) rather than silently wrong.
3. No other open questions — the two architecturally significant questions (CRUD classification, TDEE-consumption deferral) were resolved by `architecture-agent` before this plan was written (§1).

## Addendum — 2026-08-29: `ExerciseLogged` is not published on delete

Found during implementation review (`reviewer-agent`): the implementer resolved, on their own judgment during execution, that soft-deleting an exercise entry publishes no event — only `POST` (create) and `PATCH` (correction) publish `ExerciseLogged`. Neither this plan's §1 acceptance criteria nor §5 explicitly decided this either way, so it wasn't a pre-resolved question the way the CRUD classification and TDEE-consumption deferral were.

`architecture-agent` confirmed this is not an ADR-0002 violation: CLAUDE.md §2.3's "every state change is captured as a Domain Event" language is scoped to the CQRS/ES-mandatory services (`diary-service`/`profile-service`); for an event-driven-CRUD service, publishing an event is documented as a side effect, not a structural requirement for every mutation. `reviewer-agent` separately flagged the product-correctness angle: `diary-service`'s own soft-delete convention (`FoodEntryDeleted`, `WaterIntakeRemoved`, `MealPlanRemoved`) *does* publish an event for every removal, so "matching diary-service's convention" (this plan's original §1.3 wording) is only half true here — the tombstone mechanic matches, the removal-is-observable-to-consumers half does not.

**Decision (this addendum):** ship as implemented for this MVP — there is no live consumer of `ExerciseLogged` today (`nutrition-calculation-service`'s TDEE-adjustment consumption is itself deferred, §1), so there is nothing to notify. This is **not** a closed question for later, though: whatever future plan wires `nutrition-calculation-service`'s consumption of `ExerciseLogged` for real TDEE adjustment must first decide how a deleted exercise entry is surfaced to that consumer (a new `ExerciseDeleted`/`ExerciseRemoved` event is the most likely shape, matching `diary-service`'s precedent, rather than requiring that future consumer to poll/reconcile against `activity-service`'s list API) — track this explicitly as a prerequisite of that future work, not something to rediscover from scratch.
