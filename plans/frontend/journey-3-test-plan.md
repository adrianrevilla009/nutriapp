# Test Plan — `frontend` journey 3 (upgrade to Pro → publish a recipe → another user finds it)

**Stage:** 4 (Test Plan) of the human-in-the-loop pipeline, CLAUDE.md §6.
**Approved:** 2026-09-11, by adrianrg1996@gmail.com.
**Implements:** `/plans/frontend/journey-3-implementation-plan.md` (as persisted, including §9 resolutions 1-9).

No test code written yet — cases only, per TDD. Scoped to journey 3's new/modified surfaces; journeys 1-2's existing suites continue unchanged and are not re-specified. Same test-type shape as journeys 1-2 (Vitest unit, Testing Library + MSW integration, axe-core, Playwright E2E) — no new tooling.

**Resolution 7 finding (from research, read `update_recipe.py`/`domain/entities/recipe.py` directly): editing an already-published recipe is not blocked.** `UpdateRecipeHandler` has no `is_published` check — recomputes totals from the new ingredient list and saves unconditionally. `Recipe.update()`'s own docstring: "Editing ingredients/instructions/servings/title never changes publish state — an already-published recipe stays published with its (recomputed) totals." Since `search_published` reads the same row, an edit to a published recipe is immediately live in cross-user search. This shapes §3's test cases below — a pre-submit warning is the only mitigation, not a backend block.

---

## 1. Unit test cases — Zod schemas

Fixtures shaped directly from `billing_schemas.py` and `recipe_schemas.py`, not hand-invented.

- **`CheckoutSessionRequestSchema`**: `successUrl`/`cancelUrl` required; `customerEmail` optional.
- **`CheckoutSessionResponseSchema`**: `stripeSessionId`/`checkoutUrl` required.
- **`RecipeIngredientRequestSchema`**: `catalog_product_id` UUID; `quantity_grams` rejects `0` and negative (mirrors backend's `gt=0`).
- **`CreateRecipeRequestSchema`/`UpdateRecipeRequestSchema`**: `title` 1-255 chars; `instructions` non-empty; `servings` positive integer; `ingredients` array — **schema itself allows empty** (backend has no minimum) — the ≥1 UI guard is a separate frontend-only concern (§2), not encoded in the schema.
- **`NutrientTotalsResponseSchema`**: `macros_status`/`micronutrients_status` accept only `available|partial|unavailable`; `micronutrients` accepts `null` and `dict[str, number|null]`.
- **`RecipeResponseSchema`**: full field mirror incl. `is_published: boolean`, `unpublished_at: datetime|null`.
- **Error schema**: `{error, code}` fixtures for every code both services actually emit (`NOT_ENTITLED`, `SUBSCRIPTION_ALREADY_ACTIVE`, `RECIPE_NOT_FOUND`, `UNRESOLVABLE_INGREDIENT`, `INVALID_QUANTITY`, `INVALID_SERVINGS`, `CATALOG_SERVICE_UNAVAILABLE`, `ENTITLEMENT_CHECK_UNAVAILABLE`) — never an invented code.

## 2. Unit test cases — pure helpers

**`lib/api/recipes.ts` error handling:**
- `402`/`NOT_ENTITLED` mapped to a distinguishable typed error (not folded into generic `ApiError`) — asserted via `instanceof`/discriminant, not a string-match.
- Every other code maps to the existing generic `ApiError` shape — contrast test.

**`lib/api/billing.ts`:**
- `createCheckoutSession` request shape exact-match tested.
- `409`/`SUBSCRIPTION_ALREADY_ACTIVE` mapped to its own distinguishable typed error.

**Ingredient-row mapping**: quantity coercion rejects empty string, non-numeric, negative, zero before submit is possible.

**Zero-ingredient submit guard** (`canSubmitRecipe(ingredients)`): empty array → `false`; ≥1 valid row → `true`. Documented as a frontend-only opinion, not a backend contract assumption.

## 3. Integration test cases (Testing Library + MSW)

**`CheckoutRedirectButton`:**
- Click → `createCheckoutSession` called with `successUrl`/`cancelUrl` built from `NEXT_PUBLIC_APP_BASE_URL`.
- Success → `window.location.assign(checkoutUrl)` called with the exact returned URL (spied, never a real navigation).
- `409`/already-Pro → no `location.assign`; navigates to `/recipes` with an "already Pro" message.
- `401` → same re-auth handling journeys 1-2 established.
- Pending state disables double-click.

**`ProSuccessBanner`/`ProCancelBanner`:**
- Success page: "processing, may take a moment" copy, never a false "You're now Pro!" confirmation (ties to resolution 3).
- Cancel page: neutral "no charge" copy + link back to `/pro`.

**`RecipeForm`:**
- Empty ingredients → submit disabled, `aria-describedby` guidance.
- Valid submit → exact `CreateRecipeRequest` asserted field-by-field, **structurally proving no totals field is ever sent** from the client.
- **Edit mode on an already-published recipe**: submit shows an explicit pre-submit warning that changes take effect immediately with no re-publish step; submit gated behind acknowledging it. Distinct from create-mode/unpublished-edit (no warning there).
- Per-ingredient quantity `<=0` blocked before submit.

**`IngredientPicker`** (`ProductSearchBox` in `mode="select"`):
- `mode="select"` renders an "Add" action instead of `mode="log"`'s "Log" link; selecting adds to the list, does **not** navigate away — explicit regression test against `mode="log"`'s existing behavior.
- Selecting the same product twice: behavior resolved empirically during Stage B against `RecipeIngredient`'s actual invariants — documented, not guessed.

**`PublishRecipeButton`:**
- A confirmation step appears **before** the publish call, with explicit "becomes visible to other users" copy (CLAUDE.md §8) — clicking "Publish" alone, without confirming, makes zero API calls.
- Confirmed → publish call fires, success flips the `is_published` badge.
- `402`/`NOT_ENTITLED` → inline "Upgrade to Pro to publish" CTA; generic error banner asserted **absent** for this code.
- Other codes → existing generic error banner still renders (contrast test).

**`RecipeSearchBox`:**
- Query + results render title/servings/macro summary per result.
- `402`/`NOT_ENTITLED` → "Search is a Pro feature — Upgrade" CTA, distinguished from empty-results and generic 5xx states (three-way non-conflation test).
- Empty query blocked from submitting.

**`AppNav`**: authenticated render includes "Recipes"/"Upgrade to Pro" links **unconditionally** — no Pro-status branching exists (resolution 3).

**`route-handlers.test.ts`** (extended): checkout-sessions 401/correct URL construction/409-relay; all six recipe proxies' 401 + method/body pass-through; `/search` blocks empty `q` before any backend call.

## 4. Contract-equivalent test cases (schema-conformance, no live backend)

- `billing_checkout_session_{success,already_active}.fixture.json`.
- `recipe_{create,update,publish,search}_{success,not_entitled,unresolvable_ingredient}.fixture.json`.
- Each fixture exercised by at least one schema/unit test.

## 5. Accessibility test cases (axe-core)

- All seven new screens, relevant states (empty/populated, 402 branches).
- `RecipeNutrientTotals`: real `<table>` with `<th scope>` header association, reusing `MicronutrientTable`'s pattern.
- `IngredientPicker` select mode: fully keyboard-operable, "Add" action's accessible name includes the product name.
- Publish confirmation dialog: focus moves in, escapable, accessible label.
- Colour-only-signal check: `is_published`/`NOT_ENTITLED` carry distinct text content.
- Manual keyboard-only + screen-reader smoke pass before `/implementation-review`.

## 6. E2E test cases (Playwright)

**Known constraint (resolution 1)**: no live Stripe round-trip — checkout-initiation covered only by `CheckoutRedirectButton.test.tsx`.

**`pro-upgrade-recipe-publish-search.spec.ts`** (default CI):
- Seed: publisher + finder identities, each with a directly-seeded `active` billing-db subscription row (bypassing Stripe/webhook), reusing journey 1's seeded catalog product as the recipe ingredient.
- **Two `browser.newContext()`s in one spec**: context A (publisher) authors + confirms + publishes a recipe. Context B (finder), separate login, searches and finds it, content matching what A authored.
- Explicit cross-contamination check: context A stays authenticated as publisher throughout context B's actions.
- One **live**, non-mocked `402` case: a third, non-Pro identity hits `/recipes/search` and sees the real "Search is a Pro feature" prompt against the running stack.

**Explicitly deferred**: live Stripe checkout completion; a dedicated edit-after-publish E2E case (already covered at integration level in §3).

**Environment caveat**: requires Docker/docker-compose access, billing-service/recipe-service healthy, billing-db reachable for the seed insert. If Chromium can't launch (journey 2 found this true here), report structural soundness instead of a claimed pass.

## 7. Coverage expectation

Same **80% overall** threshold as journeys 1-2. Actual numbers reported after Stage B; a gap reported explicitly.

## 8. Fixtures

- `tests/fixtures/billing_checkout_session_{success,already_active}.fixture.json`.
- `tests/fixtures/recipe_{create,publish,search}_{success,not_entitled}.fixture.json`.
- `tests/fixtures/msw-handlers/{billing,recipe}.ts`.
- `tests/e2e/seed/`: extended with publisher/finder/non-Pro identities + billing-db subscription-row insertion.
- No unit/integration test makes a real call to any backend.

## Flagged for review (not a blocker)

1. `IngredientPicker`'s duplicate-product-selection behavior — resolve empirically during Stage B, not guessed.
2. The publish confirmation/consent-copy UI is genuinely new surface — worth a `security-agent`/`architecture-agent` look at whether checkbox vs. modal confirm is the right weight; non-blocking.
3. Resolution 7's finding means the pre-submit warning is the *only* mitigation this plan builds for edit-after-publish. Flag for `recipe-agent`/product: is a stronger guard wanted? Out of scope to decide here — proceeding with warning-only.
4. Two-identity E2E cross-contamination assertion is new test-infrastructure surface — `qa-agent` to confirm it's meaningful, not decorative.
