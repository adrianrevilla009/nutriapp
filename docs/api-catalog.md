# API Catalog

Registry of every public and internal HTTP API surface in the system.
Complements `docs/events-catalog.md` (which covers asynchronous events, not
HTTP APIs). Update this file in the same PR that adds, changes, or deprecates
an endpoint surface — enforced by `/implementation-review`.

## How to read this table

| Column        | Meaning                                                          |
|----------------|---------------------------------------------------------------------|
| Surface         | `public` (via Kong) or `internal` (service-to-service only)          |
| Owning service   | The service whose OpenAPI spec is authoritative for this path prefix  |
| Current version   | Latest non-deprecated version                                          |
| Status             | `active`, `deprecated (sunset: YYYY-MM-DD)`, `planned`                   |

## Public APIs (via Kong / BFF)

| Path prefix       | Owning service     | Current version | Status  |
|---------------------|----------------------|--------------------|-----------|
| `/api/v1/auth`         | `identity-service`      | v1                    | active    |
| `/api/v1/profile`         | `profile-service`      | v1                    | active    |
| `/api/v1/catalog`        | `catalog-service`        | v1                    | active    |
| `/api/v1/diary`             | `diary-service`         | v1                    | active    |
| `/api/v1/nutrition`         | `nutrition-calculation-service`         | v1                    | active    |
| `/api/v1/recognition`              | `food-recognition-service`              | v1                    | active    |
| `/api/v1/notifications`             | `notification-service`             | v1                    | active    |
| `/api/v1/activity/exercises`             | `activity-service`             | v1                    | active    |
| `/api/v1/analytics`             | `analytics-service` (`/plans/analytics-service/implementation-plan.md`) | v1                    | active    |
| `/api/v1/chat`                     | `nutrition-assistant-service`                  | v1                    | active    |
| `/api/v1/bff/dashboard`               | `bff-service` (ADR-0008)             | v1                    | active    |
| `/api/v1/billing`             | `billing-service` (ADR-0015)             | v1                    | active    |
| `/api/v1/recipes`             | `recipe-service` (CLAUDE.md section 2.2)             | v1                    | active    |
| `/api/v1/social`             | `social-service` (CLAUDE.md section 2.2)             | v1                    | active    |
| `/.well-known/jwks.json`             | `identity-service` (ADR-0022)        | n/a (JWK Set, not versioned) | active |

## Internal APIs (service-to-service, not routed through Kong)

| Path prefix                     | Owning service       | Consumers                    | Status  |
|-----------------------------------|-------------------------|---------------------------------|-----------|
| `/internal/v1/catalog/lookup`          | `catalog-service`            | `diary-service`, `food-recognition-service`   | active    |
| `/internal/v1/auth/tokens/{reference_id}/reveal` | `identity-service` | `notification-service` | active |
| `/internal/v1/profile/{user_id}/reveal-metrics` | `profile-service` | `nutrition-calculation-service` | active |
| `/internal/v1/billing/webhooks/stripe` | `billing-service` | Stripe (external, see Notes) | active |
| `/internal/v1/billing/entitlements/{user_id}` | `billing-service` | `recipe-service`, `social-service`, `analytics-service`, `nutrition-assistant-service` (all four real, cache-miss fallback only -- nutrition-assistant-service's own `entitlement_cache` currently has no live writer, see its README.md "Known gaps", so every request falls through to this endpoint this pass) | active |

## Notes

- **`frontend`** (`/plans/frontend/implementation-plan.md`) is the first
  frontend code in this repo and, per that plan's resolution 1, is the
  first consumer that talks to backend services **entirely through its
  own Next.js Route Handler proxies** (`app/api/{auth,catalog,diary,bff}/`)
  rather than directly from the browser — this avoids the CORS gap
  flagged in that plan's section 5/9 (no CORS middleware exists on any
  backend service; Kong is not running in `docker-compose.yml`). It calls
  four already-`active` rows above and adds no new endpoint of its own:
  `POST /api/v1/auth/register`, `POST /api/v1/auth/verify-email`,
  `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`,
  `POST /api/v1/auth/logout` (`identity-service`);
  `GET /api/v1/catalog/products/search`,
  `GET /api/v1/catalog/products/{id}` (`catalog-service`, both
  unauthenticated at the API level);
  `POST /api/v1/diary/food-entries` (`diary-service`, authenticated); and
  `GET /api/v1/bff/dashboard` (`bff-service`, authenticated). Revisit this
  proxy-everything approach once Kong is actually deployed locally/in a
  real environment (flagged for `architecture-agent` in the implementation
  plan's resolution 1).

  **Journey 2** (`/plans/frontend/journey-2-implementation-plan.md`) adds a
  fifth proxied call, same pattern, same reasoning: `POST
  /api/v1/recognition/photos/analyze` (`food-recognition-service`,
  authenticated, multipart) via a new `app/api/food-recognition/photos/analyze/`
  Route Handler. No new endpoint on `food-recognition-service`'s own side —
  this row was already `active`. `POST /api/v1/diary/food-entries` gains no
  new query/path shape, only an optional `X-Correlation-Id` header the
  frontend now sets when the entry's `source.source_type` is `ai_detected`
  (architecture-agent finding on that journey's plan), which
  `diary-service`'s existing `get_correlation_id` dependency already reads.

  **Journey 3** (`/plans/frontend/journey-3-implementation-plan.md`) adds a
  sixth and seventh proxied service, same pattern: `POST
  /api/v1/billing/checkout-sessions` (`billing-service`, authenticated) via
  a new `app/api/billing/checkout-sessions/` Route Handler — a
  Stripe-hosted Checkout Session redirect, never an embedded payment form;
  and all seven `/api/v1/recipes` routes (`recipe-service`, authenticated,
  including the two Pro-gated ones, `POST .../publish` and `GET
  /api/v1/recipes/search`) via `app/api/recipes/**` Route Handlers. No new
  endpoint on either backend service's own side — every row called was
  already `active`. Journey 3's own resolution 1: `billing-service`'s
  Stripe integration has no valid test-mode credentials in this
  environment (`docker-compose.yml`'s placeholders, already tracked as
  billing-service's own lead-time item), so no Playwright E2E spec in this
  repo exercises a live Stripe checkout round trip — only the
  checkout-initiation call (POST + relay of `checkout_url`) is covered,
  via a mocked-backend integration test. `GET
  /internal/v1/billing/entitlements/{user_id}` gains no new caller from
  this journey (the frontend never calls it directly — internal-only,
  never routed through Kong; `recipe-service` remains the caller, per its
  own already-documented row above).

- This table is intentionally sparse at project start (per CLAUDE.md section
  12, "no application code has been written yet"). Populate a row's real
  version/status the moment its OpenAPI spec is generated by FastAPI for the
  first time, never before — a "planned" row that never gets promoted to
  `active` is worse than no row at all.
- Deprecated rows must include the `Sunset` date per `docs/api-standards.md`
  section 2, and stay in this table until actually removed, not just until
  deprecated.
- `/internal/v1/profile/{user_id}/reveal-metrics` (`profile-service`,
  implementation plan Addendum 2) is deliberately NOT a reuse of
  `/internal/v1/auth/tokens/{reference_id}/reveal`'s single-shared-
  credential/no-rate-limit/no-audit-trail design — a dedicated security
  review found that insufficient for repeatedly-callable Article 9 health
  data disclosure. It uses a distinct per-caller credential, app-level
  rate limiting, a dedicated audit trail, and a dedicated NetworkPolicy on
  its own port (never Kong, never on the public API's port). Response is
  minimized to exactly `weight_kg, height_cm, age, sex, activity_level,
  goal_type`. See `services/profile-service/README.md` and
  `/plans/profile-service/implementation-plan.md` Addendum 2.
- `/api/v1/bff/dashboard` (`bff-service`, `/plans/bff-service/implementation-plan.md`)
  fans out three server-to-server calls, in parallel, to already-public
  endpoints: `GET /api/v1/diary/summary?date={date}` (`diary-service`),
  `GET /api/v1/nutrition/totals/{date}` and `GET /api/v1/nutrition/target`
  (`nutrition-calculation-service`). These are **not** a new internal-
  endpoint exception (the `/internal/v1/...` rows above) — they are the
  exact same public rows already in this table, called server-to-server
  purely to do the fan-out/composition the frontend would otherwise do
  itself in three separate requests (Open Host Service / Customer-
  Supplier, `docs/domain-glossary-and-context-map.md`). No new endpoint
  was added to either downstream service for this. `analytics-service`
  is not a `bff-service` fan-out target — trend viewing is served
  directly at `/api/v1/analytics/trends/weekly` via Kong, out of scope
  for `bff-service`'s dashboard aggregation
  (`/plans/analytics-service/implementation-plan.md` section 9, resolution 6).
- The `/internal/v1/nutrition/targets` row this table previously carried
  as `planned` (reserved for `analytics-service`) was removed, not
  promoted: `analytics-service`'s implementation plan (section 9,
  resolution 3) confirmed it gets current/historical targets entirely
  via consuming `NutritionTargetUpdated` events, with no concrete
  synchronous need surfacing during implementation. Revisit only if a
  genuine synchronous-lookup need appears later.
- `/api/v1/activity/exercises` (`activity-service`,
  `/plans/activity-service/implementation-plan.md`) covers four concrete
  routes: `POST /api/v1/activity/exercises` (log a manual entry),
  `PATCH /api/v1/activity/exercises/{entry_id}` (correct an entry),
  `DELETE /api/v1/activity/exercises/{entry_id}` (soft-delete, idempotent),
  `GET /api/v1/activity/exercises?date={date}` (list a day's entries).
  Manual exercise logging only this MVP — no wearable-provider OAuth
  connect/sync/disconnect endpoints exist yet (see
  `services/activity-service/README.md`'s "Known limitations").
- `/api/v1/recognition` (`food-recognition-service`) — renamed from an
  earlier `/api/v1/media` placeholder: `/plans/food-recognition-service/implementation-plan.md`
  (the approved implementation plan) specifies the concrete routes
  `POST /api/v1/recognition/photos/analyze` and
  `POST /api/v1/recognition/barcodes/decode`, which this row now reflects.
  No live consumer depended on the placeholder path, so no integration
  breaks from the rename.
- `/internal/v1/billing/webhooks/stripe` (`billing-service`,
  `/plans/billing-service/implementation-plan.md` section 1.2) is the ONE
  documented exception to "every `/internal/v1/...` route is never routed
  through Kong" in this entire table — Stripe itself must be able to reach
  this endpoint over the public internet (Stripe's own documented
  requirement for webhook endpoints), so Kong DOES route this one path
  publicly. It is still never JWT-gated: authenticity is verified instead
  via the `Stripe-Signature` HMAC scheme
  (https://stripe.com/docs/webhooks/signatures), never an unverified
  payload. Do not mistake the `/internal/v1` prefix here for "never
  publicly reachable" — see `services/billing-service/README.md` and the
  Helm chart's NetworkPolicy comment for the same note, so a future
  reviewer doesn't flag this as a missing-auth bug.
- `/internal/v1/billing/entitlements/{user_id}` (`billing-service`) was
  built with zero real callers (implementation plan section 1.4, same
  "publish the contract before any consumer exists" pattern as the six
  billing events in `docs/events-catalog.md`) and now has four real
  callers: `recipe-service`, `social-service`, `analytics-service`, and
  `nutrition-assistant-service` each call it (own, independently-named
  `billing_entitlement_check` circuit breaker per service) ONLY on an
  `entitlement_cache` miss — the documented synchronous fallback
  compensation path for the `ProUpgradeEntitlementPropagation` saga
  (`docs/sagas-and-distributed-transactions.md`). **Note**:
  `nutrition-assistant-service`'s own `entitlement_cache` currently has no
  live writer (no consumer of `EntitlementGranted`/`EntitlementRevoked`
  exists for that service yet, see its README.md "Known gaps"), so in
  practice every one of its requests is a cache miss and calls this
  endpoint — functionally correct (fail-safe, never stale) but without the
  latency/load benefit the other three callers get from their populated
  caches.
- `/api/v1/recipes` (`recipe-service`, `/plans/recipe-service/implementation-plan.md`)
  covers seven routes: `POST /api/v1/recipes` (author, not Pro-gated),
  `PATCH /api/v1/recipes/{recipe_id}` (edit own, not Pro-gated),
  `GET /api/v1/recipes/{recipe_id}` / `GET /api/v1/recipes?mine=true`
  (read own including drafts, not Pro-gated),
  `POST /api/v1/recipes/{recipe_id}/publish` (**Pro-gated**),
  `POST /api/v1/recipes/{recipe_id}/unpublish` /
  `DELETE /api/v1/recipes/{recipe_id}` (soft-unpublish only, idempotent,
  not Pro-gated), and `GET /api/v1/recipes/search?q=...` (**Pro-gated**,
  published recipes only). Entitlement-rejection uses `402 Payment
  Required` (code `NOT_ENTITLED`) — the first Pro-gated feature built in
  this codebase, so this is a newly-documented convention rather than a
  reuse of an existing precedent; see
  `services/recipe-service/infrastructure/http/error_mapping.py` for the
  full reasoning.
- `/api/v1/social` (`social-service`, `/plans/social-service/implementation-plan.md`)
  covers five routes: `POST /api/v1/social/follows` (follow, **Pro-gated**,
  idempotent, rejects self-follow), `DELETE /api/v1/social/follows/{followee_id}`
  (unfollow, **Pro-gated**, idempotent hard delete),
  `GET /api/v1/social/follows/following` / `GET /api/v1/social/follows/followers`
  (list own connections, not Pro-gated), and `GET /api/v1/social/feed`
  (**Pro-gated**, followed users' published recipes, newest first).
  Reuses `recipe-service`'s `402 Payment Required` / `NOT_ENTITLED`
  entitlement-rejection convention verbatim — now a repo-wide standard,
  not a per-service decision (implementation plan section 3); see
  `services/social-service/infrastructure/http/error_mapping.py`.
- `/api/v1/analytics` (`analytics-service`,
  `/plans/analytics-service/implementation-plan.md`) covers two routes:
  `GET /api/v1/analytics/trends/weekly` (logging streak + macro/water
  running totals vs. target, **not Pro-gated** -- every returned stat
  carries `sample_size`/`window_days` explicitly), and
  `GET /api/v1/analytics/reports/{report_type}?start_date=...&end_date=...`
  (CSV export/report generation, **Pro-gated**). Reuses `recipe-service`'s
  `402 Payment Required` / `NOT_ENTITLED` entitlement-rejection convention
  verbatim; see `services/analytics-service/infrastructure/http/error_mapping.py`.
