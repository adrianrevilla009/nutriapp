# Test Plan — `frontend` (first cut: scaffold + E2E journey 1)

**Stage:** 4 (Test Plan) of the human-in-the-loop pipeline, CLAUDE.md §6.
**Approved:** 2026-09-08, by adrianrg1996@gmail.com.
**Implements:** `/plans/frontend/implementation-plan.md` (as persisted, including §9 resolutions 1-7).

No test code has been written yet — this defines cases only, per TDD. Adapted from `/plans/nutrition-assistant-service/test-plan.md`'s structure to a frontend codebase's actual test types (Vitest unit, Testing Library + MSW integration, axe-core accessibility, Playwright E2E) rather than forcing a domain/application/infrastructure split this codebase doesn't have.

---

## 1. Unit test cases — Zod schemas (`schemas/`)

**`identity.ts`:** `RegisterRequest` rejects malformed email / empty password (mirrors `auth_schemas.py`'s `EmailStr`/`Field(min_length=1)`); `RegisterResponse` requires a UUID `user_id`. `VerifyEmailRequest` rejects missing `reference_id`/`secret`. `LoginResponse` requires `access_token`/`refresh_token`, defaults/accepts `token_type: "bearer"`; a response missing `access_token` is rejected, not silently coerced to `undefined`. `ErrorResponse` parses `{error, code}` — decide and test explicitly whether unknown extra fields are tolerated (`.passthrough()`) or rejected (`.strict()`); document the choice in the schema file itself so a future backend field addition doesn't silently break every client.

**`catalog.ts`:** `ProductResponse` parses two fixture variants — all-nullable-fields-populated (`nutrition_per_100g: null`, `package_size: null`, `price: null`, `barcode: null`) and all-fields-present — both must parse without error, mirroring `product_schemas.py`'s `| None` fields exactly. `NutrientPanelResponse`'s twelve fields are each independently `float | None`; a fixture with only some populated must parse. `ProductSearchResponse` requires `items`/`total`/`page`/`page_size`; empty `items: []` with `total: 0` parses.

**`diary.ts`:** `MacroSnapshotSchema` rejects a negative value in any of the four fields (mirrors `MacroSnapshot.__post_init__`'s non-negative invariant). `FoodSourceSnapshotSchema.quantity` rejects `<= 0` (mirrors `Field(gt=0)`). `LogFoodEntryRequest` requires `source`/`meal_slot`/`occurred_at`; `occurred_at` must serialize as an ISO-8601 datetime string, not a `Date` object, before it leaves the schema boundary. `FoodEntryResponse` round-trips a fixture built from the real `food_entry_routes.py` response shape.

**`bff.ts`:** `DashboardResponse`'s three envelope schemas each accept **all four combinations** that actually occur: `status: "available"` + populated `data` + `reason: null`; `status: "unavailable"` + `data: null` + `reason: "downstream_error"`; `status: "unavailable"` + `data: null` + `reason: "not_yet_computed"`. A fixture with `status: "available"` but `data: null` (a shape the real backend never sends but nothing prevents structurally) is explicitly rejected by the schema — this is the one place this plan adds a stricter invariant than the backend's own Pydantic model, and the test documents why (the UI's rendering logic in §3 depends on this pairing holding).

## 2. Unit test cases — pure helpers (`lib/api/http-client.ts`, mapping functions)

- `http-client.ts`: attaches `Authorization: Bearer <token>` only when a token is supplied, omits the header entirely otherwise (never sends `Bearer undefined`/`Bearer null` as a literal string — a real bug class). Parses a `{error, code}` error body into a typed `AppError`; a non-JSON or differently-shaped error body falls back to a generic typed error rather than throwing an unhandled parse exception. Enforces an explicit request timeout via `AbortController` (fake-timer test: a request exceeding the configured timeout is aborted and surfaces as a typed timeout error, not left pending).
- `productToLogFoodEntryRequest(product, quantityGrams, mealSlot, occurredAt)` (pure mapping helper backing `LogFoodEntryForm`): copies `product.nutrition_per_100g` into `macros_per_unit` unchanged (byte-for-field, per the plan's grounded semantics); fixes `unit: "g"`; sets `source_type: "catalog_product"`, `source_reference_id: product.product_id`. **Edge case grounded in `product_schemas.py`:** when `product.nutrition_per_100g` is `null` (a real, allowed shape), the helper returns an explicit `{ok: false, reason: "no_nutrition_data"}` result rather than constructing a request with fabricated/zeroed macros — the calling component (§3) must surface this as a blocking, visible message, never a silent zero.
- `useSession`'s token-refresh-scheduling pure function: given an access token's known expiry (15 min per ADR-0022) and a fixed clock, computes a refresh-due time safely before actual expiry (e.g. 60s margin); deterministic given the same clock input twice.
- Local-date formatting helper backing `/dashboard`'s default date: "today" is computed from the browser's local timezone, not `UTC` — a fake-timezone test (e.g. simulate `UTC-8` at 11pm local / already-next-day UTC) asserts the date sent to `getDashboard` matches the user's local calendar day, not UTC's.

## 3. Integration test cases (Testing Library + MSW)

**`RegisterForm`:** happy path (valid email/password) → success state directing the user to check their email; client-side validation blocks submission on invalid email / empty password before any network call (assert MSW handler call count `0`); a mocked 4xx from the register endpoint renders a visible error banner; submit button disabled while the request is in flight (guards double-submit).

**`VerifyEmailStatus`:** missing `reference_id`/`secret` in the URL → renders "invalid verification link" **without** ever calling the API (assert zero MSW calls); valid params → calls verify-email **exactly once**, including under a remount (guards a real React-effect double-invoke bug class); success → link to `/login`; a mocked already-verified/expired-token error → distinct explicit message, still links to `/login`.

**`LoginForm`:** happy path → redirect to `/search`. **Grounded, must-pass test:** three separately mocked failure reasons (wrong password, unverified email, locked account — all mapped by identity-service to the same generic `InvalidCredentialsError`) each render **byte-identical** error copy — an explicit test asserting the UI never invents a distinction the API doesn't provide, directly encoding the plan §4 finding.

**`ProductSearchBox` / `ProductResultList`:** empty query → guidance text, not an error state; populated results render name/brand/energy snippet; zero-result query → explicit "no products found" message, not a blank list; each result's "Log" action is an accessible link/button to `/log/[productId]` whose accessible name includes the product's own name (not a bare repeated "Log" fifty times); a simulated network failure shows a retry affordance rather than a silent empty list.

**`LogFoodEntryForm`:** happy path constructs and sends the exact `LogFoodEntryRequest` JSON shape asserted field-by-field against §2's mapping helper's output; `quantity <= 0` blocked client-side before any network call; a product fixture with `nutrition_per_100g: null` renders the blocking "can't log — no nutrition data" state from §2, submit button disabled; a mocked 422 from diary-service surfaces inline, tied to the offending field via `aria-describedby`; success renders the "logged — your dashboard may take a moment to update" notice (§5 of the implementation plan) plus a link to `/dashboard`.

**`dashboard/page.tsx` (client refresh component):** three independent-section rendering tests: (a) all three `"available"` → correct numbers rendered; (b) `nutrient_totals` `"unavailable"`/`"downstream_error"` while the other two are `"available"` → only that one section shows a degraded state, the other two render normally (proves independence, not a global fallback); (c) `"unavailable"`/`"not_yet_computed"` renders **visibly different copy** than `"downstream_error"` for the same section — the two reasons mean different things to the user ("still catching up" vs. "something's wrong") and must not collapse to identical text. Manual "Refresh" control triggers a real refetch (assert the mocked fetch handler's call count increases, not just relying on TanStack Query's background `staleTime` revalidation).

**`middleware.ts` / route protection:** an unauthenticated request to `/search`, `/log/[productId]`, or `/dashboard` redirects to `/login`; an authenticated request renders the target route.

## 4. Contract-equivalent test cases (schema-conformance, no live backend)

Per implementation plan §7, this codebase has no separate Pact-style contract stage — conformance is enforced by running every Zod schema in §1 against **fixtures copied verbatim from the real backend response shapes read during planning** (not hand-invented), each committed under `tests/fixtures/`:

- `register_response.fixture.json`, `login_response.fixture.json`, `verify_email_response.fixture.json` — shaped from `auth_schemas.py`.
- `product_search_response.fixture.json` (≥2 items, one with all-null optional fields) — shaped from `search_schemas.py`/`product_schemas.py`.
- `food_entry_response.fixture.json` — shaped from `diary_schemas.py`.
- `dashboard_response.fixture.json` × 3 variants (all-available; mixed availability; all-unavailable) — shaped from `dashboard_schemas.py`.
- `error_response.fixture.json` (generic `{error, code}`) — shaped from `api-conventions/SKILL.md`'s documented error shape, exercised against both a diary-service-style 422 and an identity-service-style 401.

Each fixture file carries a header comment naming the exact backend file/line it was derived from — the explicit coupling note `architecture-agent` should check on any future cross-boundary schema change (CLAUDE.md §4: "when a backend DTO changes, the corresponding Zod schema change ships in the same PR").

## 5. Accessibility test cases (axe-core)

- Every one of the six screens gets an axe-core scan (via a Vitest-compatible axe integration) in at least three states: empty/initial, populated/happy-path, and error — critical/serious violations fail the test, per `accessibility-standards/SKILL.md`.
- Beyond axe's automated checks (which can't catch every semantic gap): every form input is queried by its associated label text (`getByLabelText`), never by placeholder; `/search`'s result list is queried by `role="list"`/`"listitem"`; every interactive element is reachable via `Tab` order in a keyboard-only simulated pass; a submission error moves focus to the error summary/banner (a common, easy-to-miss a11y gap — explicit assertion on `document.activeElement`).
- Colour-only-signal check: the dashboard's "unavailable" state is asserted to carry a text label, not only a colour/icon change (grep-style assertion: the accessible text content differs between available/unavailable, not just a CSS class).
- **Manual, not automated:** a keyboard-only and screen-reader smoke pass over the full happy-path journey (register → verify → login → search → log → dashboard) before `/implementation-review`, recorded as a checklist per the skill's explicit callout of this exact journey — not scripted, but not skipped either.

## 6. E2E test cases (Playwright, against `docker-compose up`)

**`register-log-dashboard.spec.ts`** (per resolution 2 — starts from a **seeded pre-verified user**, not the real registration flow):
- Setup: a documented, test-only seed step inserts a pre-verified user directly into `identity-db` (matching identity-service's actual argon2 hash format and `email_verified` state) and at least one product into `catalog-db`, run before the Playwright suite against the compose stack — flagging this seed script itself as new test infrastructure this plan must build, not assumed to already exist.
- Steps: `/login` with the seeded credentials → land on `/search` → search for the seeded product's name → open `/log/[productId]` → submit a valid grams quantity → see the "logged" notice → navigate to `/dashboard` → **poll** (bounded retries with a real condition check, never a fixed `sleep`) until the totals reflect the logged entry, honoring diary-service's documented async-projection lag rather than asserting on the first render.
- Negative case (lightweight): wrong password on `/login` shows the generic error copy and does not navigate away from `/login`.

**Explicitly not covered by E2E this pass** (each already flagged in the implementation plan): the real `/register` → email → `/verify-email` path (resolution 2 — that screen's own logic is integration-tested in isolation per §3 instead); anything requiring Kong (not running locally); any second-locale i18n behavior.

**Environment caveat to report honestly at execution time:** this spec requires Docker/`docker-compose` access to actually run — if that access isn't available in the execution environment, the spec's existence and structural soundness will be verified (it compiles, its Playwright config is valid, a dry run against a partial/mocked stack if one is reachable) and reported as such, rather than claiming an observed full pass that didn't happen.

## 7. Coverage expectation

**80% overall** (resolution 5 — no domain/application/infrastructure split exists in this codebase to apply CLAUDE.md §3's per-layer targets to), measured across `lib/`, `schemas/`, and `components/features/`. `components/ui/` presentational primitives (Button, TextField, etc.) are lower-risk, may run below 80% individually, and that's acceptable under a single overall threshold — not a per-file gate. Actual numbers reported after Stage B rather than assumed here; if 80% isn't cleared on the first pass, the gap is reported explicitly, not silently relaxed.

## 8. Fixtures

- `tests/fixtures/*.fixture.json` — the six backend-shaped fixtures from §4.
- `tests/fixtures/msw-handlers/` — one MSW handler set per screen's integration tests, covering the happy path plus every documented error/edge shape enumerated in §3 (401, 422, the three dashboard envelope combinations, empty search results, the three-way generic-login-error case, null-nutrition-product).
- `tests/e2e/seed/` — the seed script + fixture data for the pre-verified user and the seeded catalog product (§6).
- No real call to `identity-service`, `catalog-service`, `diary-service`, or `bff-service` anywhere in the unit/integration suite — only the Playwright E2E spec touches the real stack.

## Flagged for review (not a blocker)

1. **Token storage strategy** (httpOnly-cookie refresh + in-memory access token) is not yet reviewed by `security-agent` — this test plan tests the mechanism's *behavior* but not its security posture; that review should happen during Stage B, not after.
2. **CORS/edge-routing via Next.js Route Handler proxies** means every "integration" test in §3 mocks the Route Handler boundary, not a real proxied call to a live backend — `architecture-agent` should confirm this doesn't hide a real integration bug the E2E spec (§6) would otherwise be the only thing to catch, and revisit once Kong is actually running locally.
3. **The E2E seed script (§6) is new test infrastructure**, not a reuse of anything existing — `qa-agent` should sanity-check its approach (direct DB insert matching identity-service's real hash/verification-state format) doesn't quietly drift out of sync with identity-service's own schema over time.
4. **80% overall coverage threshold** (§7) is a first-cut default for a layerless frontend codebase — revisit with `qa-agent` once real numbers exist from Stage B.
