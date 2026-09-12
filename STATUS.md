# Project Status

Summary index of actual implementation state, per
`docs/project-status-tracking.md`. Updated as part of `/create-pr` when a
merged change moves a service from one status to another. This is a
summary, not a changelog — see git history and `docs/adr/` for detail.

## Services

| Service | Scaffolded? | Core domain implemented? | Deployed to dev? | Deployed to staging/prod? | Last significant change |
|---|---|---|---|---|---|
| `identity-service` | Yes | Yes — 139 tests passing (domain 99%, application 98%, infrastructure 91% coverage) | No — Terraform written and `plan`-validated, `apply` not yet run | No | 2026-08-24 — PR #1 merged: full hexagonal implementation (registration, login, tokens per ADR-0022, password reset, RBAC), reference for every other service |
| `profile-service` | Yes | Yes — 183 tests passing (domain 99%, application 98%, infrastructure 84% coverage) | No — Terraform written (`profile-service.tf`, mirrors `identity-service.tf`) and `plan`-validated, `apply` not yet run | No | 2026-08-27 — PR #5 merged: internal `POST /internal/v1/profile/{user_id}/reveal-metrics` endpoint for `nutrition-calculation-service` to consume biometric/goal data cross-service, served on a dedicated internal-only ASGI app/port never routed through Kong (implementation plan Addendum 2), per-caller credential + rate limiting + audit trail + exactly-6-field response minimization. Builds on PR #2's 2026-08-25 CQRS/event-sourced base (ProfileCreated, BiometricConsentGranted, WeightRecorded, BodyMetricRecorded, GoalSet, GoalUpdated) and its AES-256-GCM per-user encryption via its own KMS key per ADR-0023 |
| `catalog-service` | Yes | Yes — 104 tests passing (domain 97%, application 98%, infrastructure 89% coverage) | No — Terraform written (`catalog-service.tf`) and `plan`-validated, `apply` not yet run | No | 2026-08-28 — PR #11 merged: internal `GET /internal/v1/catalog/lookup?barcode={barcode}` endpoint (Addendum 2, `X-Internal-Service-Credential` header per identity-service's precedent) for `food-recognition-service`'s barcode flow, `docs/api-catalog.md` flipped `planned` → `active`. Builds on PR #4's 2026-08-26 base (conventional-persistence/event-driven-CRUD, multi-source pluggable ingestion via `CatalogSourcePort`: Open Food Facts + USDA FoodData Central, barcode-based dedup/merge, Postgres full-text/`pg_trgm` search per ADR-0012). No adapter for Mercadona/Carrefour/Dia/Alcampo/Eroski — no official API, ToS prohibits reproduction |
| `diary-service` | Yes | Yes — 147 tests passing (domain 97%, application 100%, infrastructure 87% coverage) | No — Terraform written (`diary-service.tf`) and `plan`-validated, `apply` not yet run | No | 2026-08-26 — PR #3 merged: full CQRS/event-sourced implementation, second ES/CQRS service after `profile-service` with a freshly-justified async-projector-via-broker choice (higher write volume) and mixed aggregate granularity (per-item for Food/Water/Meal-Plan entries, per-user for Fasting Window, to enforce the no-overlap invariant atomically). 10 domain events |
| `nutrition-calculation-service` | Yes | Yes — 139 tests passing (domain 98%, application 100%, infrastructure 94% coverage) | No — Terraform written (`nutrition-calculation-service.tf`) and `plan`-validated, `apply` not yet run | No | 2026-08-27 — PR #6 merged: event-driven-CRUD implementation per ADR-0002's explicit non-event-sourced "computed value" service, macro/micro totals from `diary-service`/`catalog-service` events, Mifflin-St Jeor goal-setting engine consuming `profile-service`'s biometric/goal data via the reveal-metrics endpoint (PR #5) |
| `food-recognition-service` | Yes | Yes — 93 tests passing (36 unit + 57 integration/contract; domain 100%, application 99%, infrastructure 97% coverage) | No — Terraform written and `plan`-validated, `apply` not yet run | No | 2026-08-28 — PR #12 merged: event-driven-CRUD implementation (ADR-0002 exception), Claude Haiku 4.5 vision call for photo detection (up to 3 candidates, confidence + portion-gram range, `status` detected/uncertain/unavailable) and local `pyzbar` barcode decode against catalog-service's new internal lookup endpoint (PR #11), both circuit-breaker-guarded. `FoodPhotoAnalyzed` (v1) published via Outbox after every attempt. Never writes to `diary-service` — every detection is a suggestion pending the user's own log call. Completes CLAUDE.md's E2E journey 2 |
| `notification-service` | Yes | Yes — 184 tests passing (domain 100%, application ~99%, infrastructure ~97% coverage) | No — Terraform written (`notification-service.tf`) and `plan`-validated, `apply` not yet run | No | 2026-09-07 — PR (this change) merged: real `NutrientDeficiencyDetected` (analytics-service) consumer added — new opt-in `nutrient_deficiency_alert` push category, same `pending_push_dispatch` quiet-hours mechanism as `new_follower`'s precedent. Template uses this service's own reviewed disclaimer copy rather than forwarding the event's raw payload text, per CLAUDE.md §8's professional-advice boundary. First of the two coordinated PRs behind `analytics-service`'s own initiative — same two-PR pattern as `social-service`'s `UserFollowed` addition (2026-08-31). Builds on that 2026-08-31 base |
| `bff-service` | Yes | Yes — 51 tests passing (domain 100%, application 97%, infrastructure 100% coverage) | No — Terraform written (`bff-service.tf`) and `plan`-validated, `apply` not yet run | No | 2026-08-29 — PR #17 merged: stateless aggregation-only backend-for-frontend (ADR-0008), `GET /api/v1/bff/dashboard` fanning out to `diary-service` + `nutrition-calculation-service`'s already-public endpoints, no database/events/business logic by design. Completes Phase 1 — all 8 Phase 1 services (`identity`, `profile`, `catalog`, `diary`, `nutrition-calculation`, `food-recognition`, `notification`, `bff`) are now implemented and merged |
| `activity-service` | Yes | Yes — 76 tests passing (32 unit + 26 integration + 18 contract; domain 93%, application 100%, infrastructure 96% coverage) | No — Terraform written (`activity-service.tf`) and `validate`-clean, `apply` not yet run | No | 2026-08-29 — PR #21 merged: event-driven-CRUD implementation (ADR-0002 exception), first Phase 2 service. Manual exercise logging only (log/correct/soft-delete/list) — no wearable provider adapters (`WearableProviderPort` defined, zero implementations; no real OAuth developer-account credentials for Apple Health/Google Fit/Fitbit/Garmin, tracked in `docs/vendor-risk-register.md`). `ExerciseLogged` (v1) published on create/correct, deliberately not on delete (dated plan addendum) since `nutrition-calculation-service`'s TDEE-adjustment consumption is itself deferred and there's no live consumer yet |
| `recipe-service` | Yes | Yes — 112 tests passing (unit + integration via testcontainers Postgres/RabbitMQ + contract; domain 100%, application ~99%, infrastructure ~87-91% coverage) | No — Terraform written (`recipe-service.tf`) and `validate`-clean, `apply` not yet run | No | 2026-08-30 — PR #25 merged: event-driven-CRUD implementation (ADR-0002 exception) per ADR-0015, recipe authoring against `catalog-service`'s public product endpoint with server-only computed macro/micro totals (own local copy of `nutrition-calculation-service`'s formula, never caller-supplied — structurally guarded). Publish/search Pro-gated (first `402`/`NOT_ENTITLED` convention in the repo) via a locally-cached entitlement flag fed by `billing-service`'s `EntitlementGranted`/`EntitlementRevoked` — the first real consumer implementing the `ProUpgradeEntitlementPropagation` saga's fan-out — falling back to billing-service's internal endpoint only on a cache miss, with the fallback result never written back to the cache (structural, not just tested). Unpublish/delete always soft, never a hard row delete. `RecipeUnpublished` added as a new documented event. `macros_status` field added during review (mirroring `micronutrients_status`) so incomplete macro data is never silently reported as zero with no signal |
| `social-service` | Yes | Yes — 87 tests passing (39 unit + 34 integration + 14 contract; domain 100%, application 100%, infrastructure 87% coverage) | No — Terraform written (`social-service.tf`) and `validate`-clean, `apply` not yet run | No | 2026-08-31 — PR (this change) merged: event-driven-CRUD implementation (ADR-0002 exception), one-way follow connections (`POST`/`DELETE /api/v1/social/follows`) and a Pro-gated activity feed (`GET /api/v1/social/feed`) composed fan-out-on-read from a local `feed_entries` projection consuming `recipe-service`'s `RecipePublished`/`RecipeUnpublished` (never a synchronous call, never bff-service business logic per ADR-0008). Entitlement gating reuses `recipe-service`'s cache-first/fallback-never-cached pattern verbatim — second real consumer of the `ProUpgradeEntitlementPropagation` saga's fan-out. Unfollow is a genuine hard delete (deliberate deviation from recipe-service's soft-delete-only convention — a follow relationship has no history value once ended). Paired with a small, separately-landed PR adding a real `UserFollowed` consumer to the already-merged `notification-service` (two-PR initiative, implementation plan §6) — `RecipePublished`'s current payload carries no `title`, so `feed_entries.title` is honestly `None` until a future `RecipePublished` v2 |
| `billing-service` | Yes | Yes — 108 tests passing (56 unit + 25 contract + 27 integration; domain 100%, application 99%, infrastructure 85% coverage) | No — Terraform written (`billing-service.tf`) and `plan`-validated, `apply` not yet run | No | 2026-08-29 — PR #23 merged: event-driven-CRUD implementation (ADR-0002 exception) per ADR-0015, Stripe subscription lifecycle via hosted Checkout Sessions (PCI scope minimization) and signature-verified idempotent webhook consumption (`checkout.session.completed`, `invoice.paid`, `customer.subscription.created/deleted`, `invoice.payment_failed`). Six domain events (`SubscriptionStarted`/`Renewed`/`Cancelled`/`PaymentFailed`, `EntitlementGranted`/`Revoked`) published via Outbox, flipped to `Active` in `docs/events-catalog.md` — `recipe-service`/`social-service`/`analytics-service` documented as not-yet-consuming since none exist yet. `GET /internal/v1/billing/entitlements/{user_id}` built now (not deferred) as the `ProUpgradeEntitlementPropagation` saga's synchronous fallback. Cancellation never immediately revokes entitlement — deferred to `current_period_end` via a scheduled worker, mirroring `notification-service`'s precedent. Fixed during review: `customer.subscription.created` added as a 5th webhook so the real Stripe period value always wins over an initial 30-day estimate, preventing premature entitlement revocation. `docs/data-protection-and-privacy.md` extended with payment-data handling (ADR-0015 follow-up) |
| `analytics-service` | Yes | Yes — 97 tests passing (76 unit+contract + 21 integration; domain 99%, application 98%, infrastructure 85% coverage) | No — Terraform written (`analytics-service.tf`) and `validate`-clean, `apply` not yet run | No | 2026-09-07 — PR (this change) merged: first implementation, CQRS read-side only (ADR-0002 addendum) consuming events from `diary-service`, `profile-service`, `nutrition-calculation-service`, `billing-service` into local read projections. `GET /api/v1/analytics/trends/weekly` (not Pro-gated, streak + running macro/water totals, every stat carrying `sample_size`/`window` at the type level). Nutrient-deficiency detection publishes `NutrientDeficiencyDetected` (v1) via Outbox on a sustained breach (≥5-of-7-days below target, 14-day cooldown) — explicit dev-default threshold, not clinically reviewed, `security-agent` sign-off required before staging/prod. **Known gap**: only `protein_g`/`fat_g` have real target data flowing through the mechanism today — `NutritionTargetUpdated` publishes no micronutrient `target_min`, so true vitamin/mineral deficiency detection isn't functionally live yet despite the mechanism being generic (see `domain/tracked_nutrients.py`). `GET /api/v1/analytics/reports/{report_type}` + CSV export Pro-gated, cache-first entitlement check against `billing-service` (never writes back to cache on fallback, structurally enforced), every export audit-logged per CLAUDE.md §2.8. Paired with a small, separately-landed PR (#31) adding a real `NutrientDeficiencyDetected` push consumer to `notification-service` (two-PR initiative, implementation plan §6) |
| `nutrition-assistant-service` | Yes | Yes — 179 tests collected (up from 149): 103/103 unit tests passing this pass (domain 97%, application 100% coverage); the newly added/extended integration tests (billing events consumer idempotency+DLQ, migration `0002`, widened `entitlement_cache` upsert) collect cleanly but were not executed in this environment (no local Docker) — re-run the full testcontainers-based integration suite in CI to reconfirm the previously-verified 54-test integration baseline still passes alongside these additions before considering this fully verified | No — Terraform written (`nutrition-assistant-service.tf`, new `modules/qdrant/`) and `validate`-clean, `apply` not yet run | No | 2026-09-11 — added the `entitlement_cache` live writer: an idempotent `BillingEventsConsumer` (on `ResilientTopicConsumer`) for `EntitlementGranted`/`EntitlementRevoked`, mirroring `analytics-service`'s existing consumer, with a new `processed_entitlement_events` table/repository (additive migration `0002`) and `EntitlementCacheRepositoryPort.set()` widened to `upsert(user_id, entitled, occurred_at)` to preserve the event's own timestamp. Closes the fast-follow gap flagged at 2026-09-07 first implementation (below) — every chat request no longer needs the synchronous `EntitlementCheckPort` fallback on a warm cache. `docs/events-catalog.md` updated: this service is now the fourth real consumer of both events. Reviewed APPROVED by `reviewer-agent` and `qa-agent` before commit. 2026-09-07 — first implementation, last of the 14 bounded contexts. Conventional persistence/event-driven CRUD (ADR-0002), consuming `diary-service`/`nutrition-calculation-service`/`analytics-service` events into structured history projections — first service to use Qdrant (self-hosted, shared platform instance) and second to call an LLM (Claude Haiku 4.5, cheapest tier, same precedent as `food-recognition-service`). Embeddings via self-hosted `sentence-transformers/all-MiniLM-L6-v2` (Apache-2.0, no new vendor/DPA). `POST /api/v1/chat` Pro-gated, cache-first entitlement check against `billing-service`. Both release-blocking test categories (cross-user isolation, professional-advice-boundary disclaimer) pass, structurally enforced against a fake LLM response to prove it's not model-trusted. **Known gaps**: rule-based health-topic classifier has real precision/recall limits, flagged for `security-agent` review before staging/prod, same posture as `analytics-service`'s deficiency threshold; knowledge-base seed content (9 files) explicitly marked `STATUS: DRAFT`, pending human/professional review before production use. Completes all 14 backend bounded contexts |
| `frontend` | Yes | Yes — **all 3 of CLAUDE.md §3's named E2E journeys implemented**: (1) register → log from catalog search → see totals; (2) upload a photo → AI detects → logged with computed nutrients; (3) upgrade to Pro → publish a recipe → another user finds it in search. Combined: 264/264 unit+integration tests passing on journey 3 alone (120 unit + 131 integration + axe-core throughout), 97.69%/90.34% stmt/branch coverage; journeys 1+2 each independently verified in their own PRs (100 and 165 tests respectively). Journey 3 (2026-09-11): `NOT_ENTITLED`/`SUBSCRIPTION_ALREADY_ACTIVE` surfaced as genuinely distinguishable typed errors (never a raw error banner); recipe macros always server-computed, never client-supplied (structurally proven — no totals field in the create/update request); a real, found-not-guessed backend behavior — editing an already-published recipe is unblocked and goes live in cross-user search immediately, no re-publish step — mitigated with a pre-submit acknowledgment checkbox (the plan's only committed mitigation, no stronger guard added). Verified live against the real stack: publisher creates+publishes a recipe, a **separate finder identity** finds it via search, a **third non-Pro identity** gets a real live `402`, and the entitlement cache-miss→billing-service-internal-endpoint fallback is confirmed working end-to-end against a directly-seeded subscription row (no live Stripe keys exist in this environment — checkout-initiation is UI/proxy-verified only, real checkout completion is a tracked `devops-agent`/`billing-agent` follow-up). First-ever frontend code in this repo (Next.js 15, TypeScript strict, TanStack Query, Zod, `next-intl`); all browser-facing calls proxy through this app's own Route Handlers (no Kong/CORS dependency yet). Everything beyond the 3 named journeys (barcode logging, chat, social, water/fasting/meal-planning, wearables) remains explicitly deferred | No — Terraform written (`frontend.tf`) and `validate`-clean, Helm chart `lint`/`template`-clean (7 downstream egress targets), `apply`/`install` not yet run | No | 2026-09-11 — journey 3 landed, completing all 3 frontend E2E journeys. **2026-09-12 update**: all 3 Playwright E2E specs now run for real, every PR, via a new `e2e-journeys` job in `frontend-ci.yml` against a full 9-service `docker compose` stack (PR #45, merged) — the first time this many services have been jointly verified running together. Getting there took 3 real fixes on the first 3 live CI runs: a missing `working-directory: frontend` on the argon2-rebuild step, `alembic` invoked via its shebang'd console script instead of `python -m alembic` (the same builder/runtime-stage shebang bug already fixed for every service's uvicorn startup command, never previously applied to migration invocations), and 4 genuine Playwright strict-mode/false-positive test bugs in the journey-2/3 specs themselves (an aria-label-overridden accessible name, Next.js's own always-present route-announcer div matching `role="alert"`, and two multi-match locators needing `.first()`/scoping) — all fixed, all green now. PR #44 (merged) added `frontend`'s pod selector to the ingress `NetworkPolicy` of all 7 downstream services (identity/catalog/diary/bff/food-recognition/billing/recipe) — verified via real `helm lint`/`helm template`, not yet applied to any cluster. **Still open**: no manual keyboard/screen-reader accessibility pass has been done yet. Two tracked backend design questions, neither blocking: (a) should `ai_detected` entries instead be `catalog_product` + a separate `ai_analysis_id` field, to restore micronutrient eligibility; (b) is the edit-after-publish pre-submit-warning-only mitigation sufficient, or does product want a stronger guard. Token-storage mechanism reviewed and cleared 2026-09-08 (`security-agent`). No design system/visual identity beyond a minimal accessible default |

## Cross-Cutting

### Terraform modules

All modules below exist as code and pass `fmt`/`validate`/`tflint`/
`checkov` (275 passed, 0 failed) and a combined `terraform plan` (84 to
add, 0 to change, 0 to destroy). **None have been `apply`'d to any
environment** — that is a human-only action per CLAUDE.md §7, not yet
taken.

| Module | Exists (code) | Applied to `dev` | Applied to `staging`/`prod` |
|---|---|---|---|
| `bootstrap` (remote state) | Yes | No | No |
| `vpc` | Yes | No | No |
| `eks` | Yes | No | No |
| `rds` | Yes | No | No |
| `elasticache` | Yes | No | No |
| `secrets` | Yes | No | No |
| `scale-to-zero` | Yes | No | No |
| `ecr` | Yes | No | No |

A duplicate `cross_service_reveal_credentials` declaration in
`infra/terraform/environments/dev/{variables,main}.tf` broke
`terraform validate`/`plan` outright after two independent branches
(profile-service Addendum 2, nutrition-calculation-service PR #6) each
reconciled their own copy and both survived the merge — fixed 2026-08-28
in PR #10.

**RESOLVED 2026-09-08:** the shared `_lib` Helm chart's `env:`/`envFrom`
gap flagged in PR #12 is fixed. `identity-service`, `catalog-service`,
`diary-service`, `nutrition-calculation-service`, and `profile-service`'s
`values.yaml` now declare `env:` as a proper `[{name, value}]` list
(previously a flat map `_deployment.tpl` mis-rendered) and wire `envFrom`
to their own `ExternalSecret`-backed Secret (`profile-service` already had
`envFrom` correct; only its `env:` shape was broken). Verified via
`helm template` + a parsed inspection of the rendered `env`/`envFrom`
fields on all five charts, not just `helm lint`.

**RESOLVED 2026-09-08:** the `bff-service` → `diary-service`/
`nutrition-calculation-service` `NetworkPolicy` ingress gap flagged during
`bff-service`'s implementation review is fixed — both target services'
ingress `NetworkPolicy`s now also allow `bff-service`'s pod selector
alongside Kong's. Verified via `helm template` on all three charts,
confirming the rendered rules exist on both sides with matching labels.

**RESOLVED 2026-09-08 (discovered during frontend E2E work, closed in two
passes the same day):** all 11 services with a `packages/shared-contracts`
build dependency (`diary-service`, `nutrition-calculation-service`,
`bff-service`, `analytics-service`, `food-recognition-service`,
`notification-service`, `activity-service`, `billing-service`,
`recipe-service`, `social-service`, `nutrition-assistant-service`) had a
broken venv shebang between the build and runtime stages (`uv sync` bakes
an absolute shebang pointing at the builder stage's path into every
`.venv/bin/<script>`, which doesn't exist in the runtime stage) — every
container crashed on start with `exec: no such file or directory`. The
first 5 were found and fixed via `docker build`/`docker compose up`
verification during frontend E2E work; an `architecture-agent` review
pass the same day found the remaining 6 had never actually been
build-verified and carried the identical bug. Fixed by invoking
`python -m uvicorn` instead of relying on the venv's own shebang'd
entry-point script, across all 11 services. Verified with a real
`docker build` + `docker run`/`docker compose up` for each, confirming
`Application startup complete` and a real `200` from `/health/live`, not
just a successful build. `.claude/skills/containerization/SKILL.md`'s
reference template — the actual root cause of the bug recurring via
copy-paste — updated to show the correct form with an explanation, so a
future service's Dockerfile doesn't regress it. `catalog-service`,
`identity-service` (no `shared-contracts` dependency, builder/runtime
`WORKDIR` already match) and `profile-service` (never invokes the
`uvicorn` console script at all) were never affected.

**RESOLVED (stale entry corrected 2026-09-12):** the line above previously
said "no service's CI runs its built image at all today" — that was
already false by the time it was re-checked: PR #40 had added a smoke
step (`docker run` + curl `/health/live`) to every one of the 14 real
per-service `build-image` jobs. `db-provision-image-ci.yml` (the one
workflow without it) was investigated specifically and confirmed correct
as-is — it builds a one-shot DB-provisioning image with no HTTP server,
so a `/health/live` check doesn't apply; it already has the right
equivalent (a tool-availability smoke test for `psql`/`aws`/`python3`).

Also fixed, same investigation: `identity-service`'s Alembic migration
needs a Postgres role (`identity_service_audit_writer`) `docker-compose.yml`
never provisioned — added a `db-init/*.sql` script mounted into
`/docker-entrypoint-initdb.d/`, verified against a freshly recreated
volume. `diary-service` was missing its `RABBITMQ_URL`/`IDENTITY_JWKS_URL`
env vars in `docker-compose.yml` and its whole section in `.env.example`
— added, verified by running its migration and confirming a clean outbox
relay with no connection errors on a live RabbitMQ.

A local `docker compose up` of `identity-db`/`catalog-db`/`diary-db`/
`nutrition-db`/`rabbitmq`/`identity-service`/`diary-service` from a fully
fresh set of volumes now works end-to-end — this is the first time the
full local stack has actually been verified running together rather than
each service only being checked in isolation.

### MCP servers

Per `docs/mcp-servers.md`: all entries remain disabled. None connected in
this project to date.

### ADRs

All 23 ADRs are **Accepted** (0001–0023). None Proposed or Superseded.
Most recent: ADR-0023 (Per-Service Ownership of Erasable-Data Encryption
Keys), accepted 2026-08-25 alongside `profile-service`'s merge.

### CI/CD

CI had silently never run end-to-end since PR #1 — broken GitHub Action
SHA pins failed every job at "Set up job" without blocking merges. Fixed
2026-08-27; PR #7 then hardened `/implementation-review` to require the
actual GitHub Actions + SonarCloud Quality Gate state (not just the diff)
before a PR is APPROVED. PRs #8–#9 cleared the resulting backlog of 246
real SonarCloud findings that had gone undetected while CI was broken
(exception-test structure, fixture decorator style, event-handler method
naming, docker/query annotation nits). Quality Gate is green on `main`.
