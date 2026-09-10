# Test Plan — `frontend` journey 2 (photo upload → AI detection → logged entry)

**Stage:** 4 (Test Plan) of the human-in-the-loop pipeline, CLAUDE.md §6.
**Approved:** 2026-09-10, by adrianrg1996@gmail.com.
**Implements:** `/plans/frontend/journey-2-implementation-plan.md` (as persisted, including §9 resolutions 1-7).

No test code has been written yet — this defines cases only, per TDD. Scoped to journey 2's new/modified surfaces only; journey 1's existing suite (`/plans/frontend/test-plan.md`) continues to run unchanged and is not re-specified here. Same test-type shape as journey 1 (Vitest unit, Testing Library + MSW integration, axe-core, Playwright E2E) — no new tooling introduced.

---

## 1. Unit test cases — Zod schemas (`schemas/food-recognition.ts`)

Fixtures shaped directly from `services/food-recognition-service/infrastructure/http/schemas/recognition_schemas.py`, not hand-invented.

- **`FoodCandidateSchema`**: parses a fixture with `name`, `portion_range_min_g`, `portion_range_max_g`, `confidence` (all required); rejects `confidence` outside `[0, 1]`; rejects a negative `portion_range_min_g`/`portion_range_max_g`; a fixture where `portion_range_min_g > portion_range_max_g` — decide and test explicitly whether the schema itself rejects an inverted range or the frontend trusts the backend and only guards it defensively in the rendering component; document the choice in the schema file, same convention `bff.ts`'s stricter-than-backend envelope check already established in journey 1.
- **`AnalysisStatusSchema`**: accepts exactly `"detected"`, `"uncertain"`, `"unavailable"`; rejects any other string.
- **`AnalyzePhotoResponseSchema`**: three fixture variants — `"detected"` with 1-3 candidates (at least one `confidence >= 0.6`); `"uncertain"` with 1-3 candidates (all `confidence < 0.6`); `"unavailable"` with `candidates: []`. A fourth, explicitly-rejected fixture: 4 candidates — schema enforces `.max(3)`. `analysis_id` must be a UUID string; `model_version` a non-empty string.

## 2. Unit test cases — pure helpers

**`lib/diary-mapping.ts` — `productToLogFoodEntryRequest`'s new `sourceOverride` branch:**
- No `sourceOverride` → unchanged behavior (regression guard against journey 1's existing assertions).
- `sourceOverride` with a product that **has** full `nutrition_per_100g` → `{ok: true, request}` with `source.source_type === "ai_detected"`, `source.source_reference_id === analysisId`, and `snapshot.name`/`brand`/`macros_per_unit` still from the **product**, never from any AI-candidate-shaped input (asserted structurally — the function's signature doesn't even accept a candidate object).
- `sourceOverride` with a product missing `nutrition_per_100g` → still `{ok: false, reason: "no_nutrition_data"}`, **identical to the no-override case** — the single most important test in this plan, proving the "never fabricate macros" guard is one code path. Written as a parameterized/shared test run against both branches with the same assertion body.
- `quantityGrams` behavior unchanged regardless of `sourceOverride`.

**`lib/api/food-recognition.ts` — `analyzeFoodPhoto`:**
- Constructs `FormData` with exactly one field `file`; never sets `Content-Type` manually (explicit test — a real bug class that drops the multipart boundary).
- Attaches `Authorization: Bearer <token>` only when supplied.
- Own 45000ms timeout (not `http-client.ts`'s default) — fake-timer test, independently re-verified since this is a deliberate duplication.
- Parses a non-2xx `{error, code}` body into the same `AppError` shape `http-client.ts` produces.

**`app/api/food-recognition/photos/analyze/route.ts` (exercised via `tests/integration/route-handlers.test.ts`):**
- Missing/malformed `Authorization` → `401`, zero calls to `food-recognition-service`.
- Missing/non-`Blob` `file` field → `422`-class error, no downstream call.
- File exceeding the 8MB cap → typed error before any downstream call, zero backend calls.
- Valid file → forwards with the same `Authorization` header; relays `200 detected`, `200 unavailable` (must NOT be treated as an error — backend returns `200` for it), and a genuine backend `5xx`/network failure → relayed as `502`-class.

## 3. Integration test cases (Testing Library + MSW)

**`PhotoUploadForm`:**
- Real labeled `<input type="file" accept="image/jpeg,image/png,image/webp">`, queried by `getByLabelText`.
- Valid file + submit → mutation called exactly once.
- Oversized file blocked client-side, zero MSW calls, visible `aria-describedby`-linked error.
- Wrong MIME type blocked the same way.
- Submit disabled while pending (double-submit guard).
- Mocked `"unavailable"` response → honest "couldn't analyze" state + manual-search link, NOT styled as an error (it's a `200`).
- Mocked network failure/timeout → retry affordance.

**`CandidateList`:**
- `"detected"` fixture with 3 candidates → exactly 3 list items, each queried by accessible name containing name + confidence % + portion range text.
- `"uncertain"` fixture → same structure, distinct copy/heading vs. `"detected"`.
- `"unavailable"` (`candidates: []`) → no candidate items, manual-search fallback only.
- "None of these — search manually" present and identically reachable in all three states (one shared assertion iterating all three fixtures).
- Clicking a candidate navigates to `/search` with `q`/`aiAnalysisId`/`aiCandidateName`/`aiPortionMinG`/`aiPortionMaxG` correctly encoded.
- Clicking "search manually" navigates to plain `/search` with no `ai*` params.
- Confidence asserted present as digits in rendered text for every candidate in every status — no candidate ever color/icon-only.

**`ProductSearchBox` (modified):**
- `initialQuery` set → used as input value AND already-submitted (auto-fetch on first render).
- No `initialQuery` → unchanged journey-1 behavior (explicit regression test).
- `aiContext` present → "matching your photo detection" banner renders; absent → no banner (regression).

**`ProductResultList`/`ProductResultCard` (modified):**
- `aiContext` supplied → each card's `href` includes the AI query params.
- No `aiContext` → bare `/log/{productId}` href — **explicit regression test** against journey 1's existing assertion.

**`LogFoodEntryForm` (generalized):**
- Catalog-only call site (journey 1) → byte-identical behavior to journey 1's existing test (regression proof the generalization didn't change live behavior).
- AI-context props → quantity field initial value = portion-range midpoint; helper text present, `aria-describedby`-linked; AI-sourced disclosure banner renders above form fields.
- AI-context happy-path submit → exact `LogFoodEntryRequest` with `source.source_type: "ai_detected"`, asserted field-by-field.
- AI-context + missing `nutrition_per_100g` → same blocking "no nutrition data" state as catalog path (component-level proof of the "one code path" invariant).
- Quantity `<= 0` blocking and 422-inline-error remain unchanged in both modes (regression, run once per mode).

**`AppNav` (modified):**
- Authenticated render includes "Log from photo" link to `/log/photo`; unauthenticated-render-returns-null test unchanged (regression).

**`useAnalyzePhoto` hook:**
- Success populates `data`; does **not** invalidate any TanStack Query cache key (explicit test — guards against an accidental copy-paste from `useLogFoodEntry`).
- Surfaces `mutation.isError`/`error` on a thrown error, same shape every other mutation hook exposes.

## 4. Contract-equivalent test cases (schema-conformance, no live backend)

- `tests/fixtures/analyze_photo_{detected,uncertain,unavailable}.fixture.json` — shaped from `recognition_schemas.py`, header comment naming the exact source.
- `tests/fixtures/food_recognition_error_{401,413_oversized}.fixture.json` — frontend-defined error shapes, header comment noting they're not backend-mirrored.
- Each fixture exercised by at least one schema/unit test.

## 5. Accessibility test cases (axe-core)

- `/log/photo`: axe-core scan in 4 states (initial, detected, uncertain, unavailable) — critical/serious violations fail the test.
- Modified `/search` (with `aiContext`) and modified `/log/[productId]` (AI-sourced state): additional axe-core scans on top of journey 1's existing ones.
- Every candidate in `CandidateList` reachable/activatable via keyboard alone, document order, visible focus indicator.
- File `<input>` reachable via keyboard, native file-picker not obstructed by styling.
- Submission/analysis error moves focus to the error/status region.
- Colour-only-signal check: `"detected"`/`"uncertain"`/`"unavailable"` carry different **text content**, not merely different colour/icon.
- **Manual, not automated**: keyboard-only + screen-reader smoke pass over the full journey-2 path, performed without looking at the uploaded photo or thumbnail, before `/implementation-review`, recorded as a checklist.

## 6. E2E test cases (Playwright)

**Known constraint, addressed explicitly**: `food-recognition-service`'s `ClaudeVisionAdapter` calls the real Anthropic API — a live-model call in default CI is non-deterministic and against `media-recognition-conventions SKILL.md`'s rule that live-model integration tests run on a separate, rate-limited schedule, excluded from default CI.

**`photo-log-dashboard.spec.ts` (default CI, deterministic, no live model call):**
- **Candidate → confirm → log → dashboard**: `page.route()` intercepts only the browser's call to `/api/food-recognition/photos/analyze` with a fixture `"detected"` response; every other call (`/search`, `/log/[productId]`, `/dashboard`) runs against the real `docker-compose` stack, reusing journey 1's seeded user/product (extend the seed if needed so the fixture candidate's name matches a seeded product). Full path: login → `/log/photo` → select test image → submit → intercepted candidates render → click one → `/search` prefilled/auto-submitted → seeded product appears → `/log/[productId]?aiAnalysisId=…` → banner + midpoint-prefilled quantity → submit → "logged" notice → `/dashboard` → poll (bounded retries, no fixed sleep) until totals reflect it.
- **"None of these" manual path**: upload a photo, intercept the analyze response (any status), click "search manually" → plain `/search`, no AI params → completes journey-1's catalog logging path.
- **Deterministic `"unavailable"` case, genuinely live (no interception)**: the compose stack sets `FOOD_RECOGNITION_PHOTO_ANALYSIS_ENABLED=false` for this run, making `food-recognition-service` deterministically return `"unavailable"` for real — exercises the real Route Handler, the real network hop, and the honest UI state end-to-end without a live model call.

**Explicitly deferred**: a genuinely-live-model E2E case (separate, rate-limited schedule, not this plan's default-CI scope). Barcode-decode E2E (out of scope per implementation plan §1).

**Environment caveat**: requires Docker/`docker-compose` access plus `food-recognition-service`'s own image/dependencies actually building and starting healthy. If unavailable, report structural soundness verified instead of an observed pass, same honesty standard as journey 1.

## 7. Coverage expectation

Same **80% overall** threshold as journey 1, measured across `lib/`, `schemas/`, `components/features/` including this journey's new files. Actual numbers reported after Stage B; a gap reported explicitly, never silently relaxed.

## 8. Fixtures

- `tests/fixtures/analyze_photo_{detected,uncertain,unavailable}.fixture.json`.
- `tests/fixtures/msw-handlers/food-recognition.ts` — covers all three statuses plus 401/413/502.
- `tests/e2e/fixtures/` — one small, real, low-resolution test image for Playwright's file-input interaction.
- `tests/e2e/seed/` — extended if needed so the seeded catalog product is findable by the fixture candidate's name.
- No unit/integration test makes a real call to any backend — only the Playwright E2E spec touches the real stack, and only the `"unavailable"`-flag case exercises `food-recognition-service` for real.

## Flagged for review (not a blocker)

1. The `page.route()` interception boundary in §6 is a deliberate first-cut compromise — worth `architecture-agent`/`qa-agent` confirming the granularity is right.
2. Fixture-candidate-name-to-seeded-product-name matching (§6/§8) is new test infrastructure coupling — same drift-risk category journey 1's test plan already flagged for its own seed script.
3. Confidence-in-inverted-range validation (§1) is left as an open call — resolve deliberately during Stage B.
4. `architecture-agent`'s in-flight review of `ai_detected` source-type usage may surface something relevant to §2's `sourceOverride` test cases — revisited as a follow-up if it does, non-blocking.
