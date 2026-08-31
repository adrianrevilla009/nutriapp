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
| `notification-service` | Yes | Yes — 128 tests passing (domain 100%, application 99%, infrastructure 97% coverage) | No — Terraform written (`notification-service.tf`) and `plan`-validated, `apply` not yet run | No | 2026-08-28 — PR #14 merged: CQRS read-side-only implementation (ADR-0002 addendum), transactional email (SES) for `UserRegistered`/`PasswordResetRequested`/`NewDeviceLoginDetected` via identity-service's internal reveal endpoint, push reminders via a local `reminder_schedule` projection fed by `diary-service` events + an in-service scheduler (no new call into `diary-service`, per architecture-agent). Water-intake absence reminder deliberately descoped (dated plan addendum); `NutrientDeficiencyDetected` out of scope (`analytics-service` doesn't exist yet) |
| `bff-service` | Yes | Yes — 51 tests passing (domain 100%, application 97%, infrastructure 100% coverage) | No — Terraform written (`bff-service.tf`) and `plan`-validated, `apply` not yet run | No | 2026-08-29 — PR #17 merged: stateless aggregation-only backend-for-frontend (ADR-0008), `GET /api/v1/bff/dashboard` fanning out to `diary-service` + `nutrition-calculation-service`'s already-public endpoints, no database/events/business logic by design. Completes Phase 1 — all 8 Phase 1 services (`identity`, `profile`, `catalog`, `diary`, `nutrition-calculation`, `food-recognition`, `notification`, `bff`) are now implemented and merged |
| `activity-service` | No | No | No | No | — |
| `recipe-service` | No | No | No | No | — |
| `social-service` | Yes | Yes — 87 tests passing (39 unit + 34 integration + 14 contract; domain 100%, application 100%, infrastructure 87% coverage) | No — Terraform written (`social-service.tf`) and `validate`-clean, `apply` not yet run | No | 2026-08-31 — PR (this change) merged: event-driven-CRUD implementation (ADR-0002 exception), one-way follow connections (`POST`/`DELETE /api/v1/social/follows`) and a Pro-gated activity feed (`GET /api/v1/social/feed`) composed fan-out-on-read from a local `feed_entries` projection consuming `recipe-service`'s `RecipePublished`/`RecipeUnpublished` (never a synchronous call, never bff-service business logic per ADR-0008). Entitlement gating reuses `recipe-service`'s cache-first/fallback-never-cached pattern verbatim — second real consumer of the `ProUpgradeEntitlementPropagation` saga's fan-out. Unfollow is a genuine hard delete (deliberate deviation from recipe-service's soft-delete-only convention — a follow relationship has no history value once ended). Paired with a small, separately-landed PR adding a real `UserFollowed` consumer to the already-merged `notification-service` (two-PR initiative, implementation plan §6) — `RecipePublished`'s current payload carries no `title`, so `feed_entries.title` is honestly `None` until a future `RecipePublished` v2 |
| `billing-service` | Yes | Yes — 108 tests passing (56 unit + 25 contract + 27 integration; domain 100%, application 99%, infrastructure 85% coverage) | No — Terraform written (`billing-service.tf`) and `plan`-validated, `apply` not yet run | No | 2026-08-29 — PR #23 merged: event-driven-CRUD implementation (ADR-0002 exception) per ADR-0015, Stripe subscription lifecycle via hosted Checkout Sessions (PCI scope minimization) and signature-verified idempotent webhook consumption (`checkout.session.completed`, `invoice.paid`, `customer.subscription.created/deleted`, `invoice.payment_failed`). Six domain events (`SubscriptionStarted`/`Renewed`/`Cancelled`/`PaymentFailed`, `EntitlementGranted`/`Revoked`) published via Outbox, flipped to `Active` in `docs/events-catalog.md` — `recipe-service`/`social-service`/`analytics-service` documented as not-yet-consuming since none exist yet. `GET /internal/v1/billing/entitlements/{user_id}` built now (not deferred) as the `ProUpgradeEntitlementPropagation` saga's synchronous fallback. Cancellation never immediately revokes entitlement — deferred to `current_period_end` via a scheduled worker, mirroring `notification-service`'s precedent. Fixed during review: `customer.subscription.created` added as a 5th webhook so the real Stripe period value always wins over an initial 30-day estimate, preventing premature entitlement revocation. `docs/data-protection-and-privacy.md` extended with payment-data handling (ADR-0015 follow-up) |
| `analytics-service` | No | No | No | No | — |
| `nutrition-assistant-service` | No | No | No | No | — |

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

**Known unresolved issue (flagged in PR #12, not yet fixed):** the shared
`_lib` Helm chart's `_deployment.tpl` blindly `toYaml`s `values.yaml`'s
flat-map `env:` into Kubernetes' `env:` list field (which expects
`[{name, value}]`), producing an invalid Deployment spec that neither
`helm lint` nor `helm template` catches. Separately, only
`profile-service`'s chart wires `envFrom` to its own `ExternalSecret`
Secret — identity/catalog/diary/nutrition-calculation-service's charts
don't, so `DATABASE_URL` would never reach those containers on a real
deploy. `food-recognition-service`'s own new chart uses the correct
format; the other five services' charts are **not yet backported**. A
dedicated follow-up is recommended before any real `helm install`.

**Known unresolved issue (flagged during `bff-service`'s implementation
review, not yet fixed):** `bff-service`'s chart defines an egress
`NetworkPolicy` allowing calls to `diary-service` and
`nutrition-calculation-service`, but those two services' own charts
(unmodified by this change) only allow ingress from Kong's pod selector
today, not from `bff-service`. On a real cluster, `bff-service`'s calls
to both would be blocked until their charts' ingress `NetworkPolicy`s are
updated to also allow `bff-service`'s pod selector — a follow-up for
`diary-agent`/`nutrition-calculation-agent`. Documented in the header
comment of `infra/k8s/charts/bff-service/templates/networkpolicy-egress-downstream.yaml`.
Not a blocker today since nothing is `apply`'d to a real cluster
(CLAUDE.md §7).

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
