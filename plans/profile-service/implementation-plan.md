# Implementation Plan — `profile-service`

**Status:** Approved
**Date approved:** 2026-08-24
**Stage:** 2 (Implementation Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Related:** ADR-0002 (CQRS/ES scope), `.claude/agents/profile-agent.md`, `/plans/identity-service/implementation-plan.md` (reference pattern), `/plans/platform-infra/implementation-plan.md` (shared infra reused as-is)

## 1. Scope

Build `profile-service` end-to-end: domain → application → infrastructure → tests, plus its Terraform/Helm/CI wiring, reusing the shared platform scaffolding (`infra/k8s/charts/_lib/`, shared RDS instance, root `docker-compose.yml`/`Makefile`) established by `identity-service`. No new platform-level infra needed.

**Bounded context** (per `.claude/agents/profile-agent.md`): recording a user's biometric/health metrics (weight, height, age, sex, activity level) and stated goal (lose/maintain/gain, target value, target date), and exposing the evolution timeline. No authentication/password handling (`identity-service`'s domain).

**Acceptance criteria:**
1. Consuming `UserRegistered` (v1) creates an empty profile aggregate for that `user_id` — reactive, no synchronous call to `identity-service`. Idempotent (dedup by `event_id`).
2. `POST /api/v1/profile/consent` records explicit, specific consent to collect biometric/health data (`BiometricConsentGranted`) — required before any metric can be written; not bundled with general ToS acceptance (CLAUDE.md §8).
3. `POST /api/v1/profile/metrics/weight` records a weight reading → `WeightRecorded`. Rejected with `403` if consent has not been granted.
4. `POST /api/v1/profile/metrics/body` records height, age, sex, or activity level → `BodyMetricRecorded`. Same consent gate.
5. `POST /api/v1/profile/goal` / `PUT /api/v1/profile/goal` set/update the user's goal → `GoalSet` / `GoalUpdated`.
6. `GET /api/v1/profile` returns the current snapshot (latest value per metric + current goal) from a read-model projection, not by replaying events on every read.
7. `GET /api/v1/profile/evolution?metric=weight&from=...&to=...` returns the timeline for graphs, from a dedicated projection.
8. The aggregate is fully reconstructible by replaying its event stream (rebuild test, per `.claude/skills/cqrs-event-sourcing/SKILL.md`).
9. A correction to a past value is a new event, never a mutation of a stored one.
10. `WeightRecorded`, `BodyMetricRecorded`, `GoalSet`, `GoalUpdated` are published via the Outbox pattern, each carrying only the specific fields needed (no over-collection).
11. Biometric field values inside event payloads are encrypted per-user (envelope encryption) so that a future erasure request can crypto-shred them — see §9.1 for the open question this raises.
12. Coverage: domain ≥ 90%, application ≥ 85%, infrastructure ≥ 70% (CLAUDE.md §3), including a projector-replay test and an idempotent-consumption test for the `UserRegistered` consumer.

## 2. Architectural classification

Per ADR-0002 and `.claude/agents/profile-agent.md`: **full event sourcing + CQRS**, the second service in the repo (after none — `identity-service` was conventional persistence) to use this pattern, and the one that establishes the concrete precedent every later ES/CQRS service (`diary-service`, later `analytics-service`'s read side) will mirror. All three hexagonal layers are touched.

## 3. Files to create or modify

```
services/profile-service/
  pyproject.toml, uv.lock, Dockerfile, .dockerignore, README.md, CLAUDE.md
  alembic.ini
  migrations/versions/0001_create_profile_tables.py
      # profile_events (event store), outbox, processed_inbound_events,
      # profile_snapshot (read model), profile_evolution (read model),
      # profile_data_keys (per-user envelope-encryption key material)

  domain/
    entities/profile.py                       # aggregate root, rebuild(events), apply()
    value_objects/weight_kg.py
    value_objects/height_cm.py
    value_objects/age.py
    value_objects/sex.py                      # enum
    value_objects/activity_level.py           # enum
    value_objects/goal_type.py                # enum: LOSE, MAINTAIN, GAIN
    value_objects/goal_target.py               # target value + optional target date
    events/profile_created.py
    events/biometric_consent_granted.py
    events/weight_recorded.py
    events/body_metric_recorded.py
    events/goal_set.py
    events/goal_updated.py
    ports/profile_event_store_port.py
    ports/profile_snapshot_read_port.py
    ports/evolution_read_model_port.py
    ports/event_publisher_port.py
    ports/outbox_repository_port.py
    ports/processed_events_port.py
    ports/data_encryption_port.py             # encrypt/decrypt a field, per-user key
    services/goal_policy.py                   # validates goal type/target combinations

  application/
    commands/create_profile_on_user_registered.py  (+ handler)
    commands/grant_biometric_consent.py             (+ handler)
    commands/record_weight.py                       (+ handler)
    commands/record_body_metric.py                  (+ handler)
    commands/set_goal.py                            (+ handler)
    commands/update_goal.py                         (+ handler)
    queries/get_profile_snapshot.py                 (+ handler)
    queries/get_evolution_timeline.py               (+ handler)
    dto/

  infrastructure/
    http/routes/profile_routes.py
    http/routes/consent_routes.py
    http/schemas/
    http/health.py
    messaging/user_registered_consumer.py
    messaging/rabbitmq_event_publisher.py
    messaging/outbox_relay_worker.py
    persistence/models.py
    persistence/postgres_event_store.py             # ProfileEventStorePort adapter
    persistence/postgres_snapshot_projector.py       # writes + reads profile_snapshot
    persistence/postgres_evolution_projector.py      # writes + reads profile_evolution
    persistence/postgres_outbox_repository.py
    persistence/postgres_processed_events_repository.py
    security/kms_envelope_data_encryption.py         # ProfileDataEncryptionPort adapter
    composition_root.py
    main.py

  tests/
    unit/domain/...       # rebuild tests, value object tests, goal_policy tests
    unit/application/...
    integration/infrastructure/...   # testcontainers Postgres: event store, both
                                      # projectors (replay test), encryption roundtrip
    contract/http/..., contract/events/...   # UserRegistered consumer contract +
                                              # producer contracts for the 4 new events
    fixtures/factories.py

infra/k8s/charts/profile-service/
  Chart.yaml, values.yaml, values-dev.yaml, values-staging.yaml, values-prod.yaml
  values.schema.json                 # copied from _lib's template from day one —
                                      # identity-service's addendum showed omitting
                                      # this lets bad values.yaml shapes pass silently
  ci/synthetic-values.yaml
  templates/ (built on infra/k8s/charts/_lib/, same as identity-service)

infra/terraform/environments/dev/profile-service.tf
    # mirrors identity-service.tf: _db-provision-job via Helm release (not Terraform
    # directly), module.ecr_profile_service via the existing infra/terraform/modules/ecr

.github/workflows/profile-service-ci.yml
    # includes a helm-lint-and-template job from the start (identity-service added
    # this only in a post-review addendum — no reason to repeat that gap here)

docker-compose.yml, Makefile          # add profile-service block / SERVICE=profile-service target

packages/shared-contracts/schemas/weight_recorded.v1.json          # new
packages/shared-contracts/schemas/body_metric_recorded.v1.json     # new
packages/shared-contracts/schemas/goal_set.v1.json                 # new
packages/shared-contracts/schemas/goal_updated.v1.json             # new
packages/shared-contracts/python/shared_contracts/events/          # add the four above

docs/events-catalog.md      # WeightRecorded/BodyMetricRecorded/GoalSet/GoalUpdated:
                             # replace the current combined placeholder entry with 4
                             # concrete, separately-versioned entries; mark Status: Active
docs/api-catalog.md         # /api/v1/profile/*: planned -> active
docs/domain-glossary-and-context-map.md   # add "Biometric Consent" term if not present
```

## 4. Ports/adapters affected

| Port (domain/application) | Adapter (infrastructure) |
|---|---|
| `ProfileEventStorePort` | `PostgresEventStore` (append/load stream for aggregate `user_id`) |
| `ProfileSnapshotReadPort` | `PostgresSnapshotProjector` |
| `EvolutionReadModelPort` | `PostgresEvolutionProjector` |
| `EventPublisherPort` | `RabbitMqEventPublisher` (faststream) — same pattern as `identity-service`, new instance |
| `OutboxRepositoryPort` | `PostgresOutboxRepository` + `OutboxRelayWorker` — same pattern, new instance |
| `ProcessedEventsPort` | `PostgresProcessedEventsRepository` — dedup for the `UserRegistered` consumer, per `.claude/skills/messaging-conventions/SKILL.md` |
| `DataEncryptionPort` | `KmsEnvelopeDataEncryption` — see §9.1, open question on key ownership |

All new; `EventPublisherPort`/`OutboxRepositoryPort` reuse `identity-service`'s established *pattern*, not its code (each service owns its own outbox table and relay worker per CLAUDE.md §2.5's "no shared schemas").

## 5. Domain events

- **`WeightRecorded` (v1, new)** — `{ "user_id", "weight_kg": "number (encrypted)", "recorded_at" }`
- **`BodyMetricRecorded` (v1, new)** — `{ "user_id", "metric_type": "height|age|sex|activity_level", "value": "encrypted", "recorded_at" }`
- **`GoalSet` (v1, new)** — `{ "user_id", "goal_type": "lose|maintain|gain", "target_value": "number | null (encrypted)", "target_date": "date | null", "set_at" }` — `target_value` corrected to encrypted per Addendum 1 below (a target weight is health-adjacent data, same as the metrics above); `goal_type`/`target_date` stay in clear, needed for business logic and not a biometric value on their own.
- **`GoalUpdated` (v1, new)** — same shape as `GoalSet`, plus `previous_goal_type`
- **Consumed: `UserRegistered` (v1)** — no schema change, `profile-service` becomes an actual (not just documented) consumer.

These replace the single generic placeholder entry currently in `docs/events-catalog.md` (lines 101–106) with four concrete, separately-versioned entries, each `Status: Active` once the contract tests pass. Requires `architecture-agent` concurrence (new/changed cross-service contract) and confirmation from `nutrition-calculation-agent`/`analytics-agent` (documented consumers) that the refined payload shapes don't break their planned integration.

## 6. Cross-service impact — flagged for `architecture-agent`

- Second full-ES/CQRS service in the repo — this plan's aggregate/projector/outbox layout becomes the concrete precedent `diary-service` will mirror later. Worth an explicit sign-off that the pattern generalizes before it's copied a second time.
- `nutrition-calculation-service` and `analytics-service` are documented consumers of these four events (`docs/domain-glossary-and-context-map.md`) but don't exist yet — no live integration to break, but the payload shapes decided here become their contract.
- The `UserRegistered` consumer is `profile-service`'s first live inbound dependency on `identity-service`'s event stream.
- **Open architectural question, not resolved by this plan** — see §9.1: the encryption-key ownership model in `docs/data-protection-and-privacy.md` (`identity-service`'s key store) doesn't exist yet anywhere in the codebase.

## 7. Resilience/caching/migration needs

- **Circuit breaker + retry + timeout**: required around `KmsEnvelopeDataEncryption`'s calls to AWS KMS (`GenerateDataKey`/`Decrypt`) per `.claude/skills/resilience-patterns/SKILL.md` — this is `profile-service`'s only synchronous external dependency. No inter-service synchronous calls (RabbitMQ is fully async here).
- **Caching**: none introduced. `GET /api/v1/profile` reads a Postgres projection already shaped for that exact query — no Redis cache justified yet (no measured latency problem to solve); revisit later if warranted, per CLAUDE.md's "no speculative caching" default.
- **Migration**: first Alembic migration, `CREATE TABLE`-only (event store, outbox, dedup table, two read-model tables, key-material table) — additive, does not trigger the destructive-change approval gate.
- **Terraform**: same shape as `identity-service.tf` — no new shared infra, just this service's chart wiring + its own ECR repo via the already-generalized `infra/terraform/modules/ecr`.

## 8. Test plan reference

See `/plans/profile-service/test-plan.md` (to follow).

## 9. Risks and open questions

**9.1 — Encryption key ownership (blocking, needs a human decision before implementation starts).**
`docs/data-protection-and-privacy.md` §4 specifies that per-user data keys for crypto-shredding are "stored in `identity-service`'s key store" — but `identity-service`'s approved implementation plan and its 139 tests contain no key-store, no KMS integration, and no account-deletion endpoint at all. That store doesn't exist. Two ways forward:
- **(a)** `profile-service` owns its own per-user data key material now (`profile_data_keys` table, KMS-wrapped), and a future cross-cutting initiative consolidates key ownership into a shared service if/when `identity-service` (or a new dedicated capability) actually builds one. Pragmatic, ships now, but deviates from the doc as written.
- **(b)** Block this plan's encryption work until a prerequisite plan adds the key store to `identity-service`, keeping the doc's design intact but delaying `profile-service`.
This plan **assumes (a)** as a provisional default, pending explicit confirmation plus `security-agent`/`architecture-agent` sign-off before `/implementation-execution` begins — it may warrant its own ADR (CLAUDE.md §9: "propose an ADR whenever a decision changes... service boundaries").

**9.2 — Erasure trigger is explicitly out of scope.** No `AccountDeletionRequested`-style event exists yet anywhere in the system (no service publishes one), and CLAUDE.md §7 requires the crypto-shredding step itself to never run without explicit human confirmation. This plan makes `profile-service`'s stored data *erasure-ready* (encrypted, keyed per user) but does **not** implement a deletion consumer/endpoint — that's cross-cutting saga work (ADR-0019) for a later, dedicated plan once the trigger exists upstream.

**9.3 — Goal validation rules.** `goal_policy.py` needs concrete rules (e.g., is a target date required for `lose`/`gain` but not `maintain`? Any bound on target value relative to current weight?) — currently unspecified in the spec. Deferred to `/test-plan`, where they'll be pinned down as concrete test cases.

**9.4 — `record_body_metric`'s single generic command vs. one command per metric.** This plan keeps one generic `record_body_metric(metric_type, value)` command mirroring the events-catalog's original generic shape, rather than four separate commands (`record_height`, `record_age`, ...). Simpler, fewer files; revisit if per-metric type safety at the command layer is preferred instead.

## Addendum 1 — 2026-08-24, §9.1 resolved + encrypted-field scope corrected

**§9.1 resolved: option (a).** `profile-service` owns its own per-user data
key material now (`profile_data_keys` table, KMS-wrapped envelope
encryption via `KmsEnvelopeDataEncryption`), rather than blocking on a
key-store that doesn't exist yet in `identity-service`. Rationale: no
service in the codebase implements account deletion or a key store today,
so blocking (option b) has no concrete prerequisite plan to wait on — it
would stall `profile-service` indefinitely rather than for a bounded time.
Each service owning its own key material is also consistent with CLAUDE.md
§2.5's "no shared schemas across service boundaries" principle already
applied elsewhere (outbox, event store: every service gets its own, never
a shared table). `docs/data-protection-and-privacy.md` §4's line "stored
in `identity-service`'s key store" is now stale against this decision —
**follow-up**: correct that doc in this service's PR to describe
per-service key ownership instead of a centralized store, and flag to
`architecture-agent`/`security-agent` at `/implementation-review` (stage
8) whether this decision rises to its own ADR (CLAUDE.md §9) given it
changes a documented cross-service design, not just an implementation
detail. Not blocking `/implementation-execution` — captured as a required
review item at stage 8/9 instead of a pre-execution gate, since the
alternative (option b) has no bounded path forward today.

**Encrypted-field scope corrected.** `GoalSet`/`GoalUpdated`'s
`target_value` is now encrypted (see §5's updated entry) — a target
weight is health-adjacent data under the same GDPR Art. 9 reasoning as
`weight_kg`/`BodyMetricRecorded.value`, and was inconsistently left in
clear in the original draft. `goal_type` and `target_date` remain
unencrypted: needed directly for `goal_policy` evaluation and query
filtering, and neither is a biometric value by itself.

## Addendum 2 — 2026-08-26, new internal reveal-metrics endpoint

**Scope added**: `profile-service` gains `POST /internal/v1/profile/{user_id}/reveal-metrics`,
called synchronously by `nutrition-calculation-service` (its own plan,
`/plans/nutrition-calculation-service/implementation-plan.md` §9.1 and its
security-agent sub-addendum) to obtain plaintext biometric values for its
Mifflin-St Jeor BMR/TDEE calculation, since ADR-0023 deliberately isolates
`profile-service`'s per-user KMS key material to `profile-service` alone.

This is **not** a reuse of `identity-service`'s `.../reveal` endpoint
pattern as-is — a dedicated `security-agent` review (conducted as part of
approving `nutrition-calculation-service`'s plan) found that precedent's
single-shared-credential, no-rate-limit, no-audit-trail design
insufficient for repeatedly-callable Article 9 health data disclosure.
Human-approved, binding requirements for this endpoint (full detail in the
other plan's sub-addendum, restated here since they land in this
service's own codebase):

1. A new, distinct per-caller Secrets Manager credential (Terraform
   `random_password`), not a shared secret.
2. A narrow, human-approved IRSA exception letting `nutrition-calculation-service`
   read exactly that one secret ARN — nothing else.
3. A dedicated port + `NetworkPolicy` for this endpoint, excluding Kong,
   restricted to `nutrition-calculation-service`'s pod selector only.
4. App-level rate limiting keyed by caller-credential + `user_id`
   (reuse `identity-service`'s `RateLimiterPort`/`RedisRateLimiter` pattern).
5. Response minimization: exactly `weight_kg, height_cm, age, sex,
   activity_level, goal_type` — a new dedicated query, not a wrapper
   around the full-profile decrypt path.
6. **A new audit-trail capability in `profile-service`** (none exists
   today) — append-only, INSERT-only DB role, recording every call
   (success and failure): `actor_id`, `action="biometric_snapshot_revealed"`,
   `target_type="profile"`, `target_id=user_id`, `outcome`,
   `metadata={"fields": [...]}` (names only, never values), `correlation_id`.
7. Never logs the response body or any field value — field names only.
8. `docs/api-catalog.md`'s Internal APIs table gets a new row.

**Files added to `services/profile-service/`**: `infrastructure/http/routes/internal_reveal_metrics_routes.py`,
`application/queries/get_biometric_snapshot_for_calculation.py` (+handler),
`domain/entities/audit_record.py` (or equivalent — first audit-trail
capability in this service), `domain/ports/audit_repository_port.py`,
`infrastructure/persistence/postgres_audit_repository.py`,
`infrastructure/persistence/postgres_rate_limiter.py` (or reuse
`identity-service`'s pattern via a shared internal package if that's
cleaner — implementer's call, not dictated here), a new Alembic migration
(`audit_records` table, append-only/INSERT-only role grant), Helm/Terraform
changes per requirements 1–3 above, and `README.md`/`CLAUDE.md` updates
documenting the new endpoint, its caller, and its audit behavior.

**Reviewed together**: this addendum's implementation and
`nutrition-calculation-service`'s implementation are reviewed together at
`/implementation-review` before either merges, since they're two halves
of one feature.
