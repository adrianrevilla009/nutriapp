# Implementation Plan — `frontend` journey 3 (upgrade to Pro → publish a recipe → another user finds it)

**Stage:** 2 (Implementation Plan) of the human-in-the-loop pipeline, CLAUDE.md §6.
**Approved:** 2026-09-11, by adrianrg1996@gmail.com.

**Related:** CLAUDE.md §3 (E2E journey 3), §8 (user-published-content consent surface); `/plans/frontend/implementation-plan.md` (journey 1) and `/plans/frontend/journey-2-implementation-plan.md` (journey 2), both merged — this plan extends that app and inherits their resolutions unless a deviation is named below; `docs/frontend-architecture.md`; `.claude/skills/accessibility-standards/SKILL.md`; `.claude/skills/feature-flags/SKILL.md`; `services/billing-service/` and `services/recipe-service/` (actual contracts, read directly); `docs/api-catalog.md`; `docs/sagas-and-distributed-transactions.md` (`ProUpgradeEntitlementPropagation`).

---

## 1. Scope

Build CLAUDE.md §3's E2E journey 3 on top of the existing frontend app: **"Upgrade to Pro → publish a recipe → another user finds it in recipe search."**

**New routes:**

| Route | Purpose | Calls |
|---|---|---|
| `/pro` | Pro upsell + "Upgrade to Pro" button | `POST /api/v1/billing/checkout-sessions` (proxied) |
| `/pro/success` | Stripe `success_url` destination | none (display only) |
| `/pro/cancel` | Stripe `cancel_url` destination | none |
| `/recipes` | List own recipes (drafts + published) | `GET /api/v1/recipes?mine=true` |
| `/recipes/new` | Author a recipe | `POST /api/v1/recipes` |
| `/recipes/[recipeId]` | View/edit own recipe, publish/unpublish/delete | `GET/PATCH /api/v1/recipes/{id}`, `.../publish`, `.../unpublish`, `DELETE` |
| `/recipes/search` | Cross-user published-recipe search | `GET /api/v1/recipes/search?q=` |

**Flow:** User A logs in → `/pro` → "Upgrade to Pro" → browser redirects to Stripe's hosted Checkout (real cross-origin navigation) → redirects back to `/pro/success` → `/recipes/new` (author, catalog-sourced ingredients, server computes all macros/micros) → `/recipes/[recipeId]` → "Publish". User B (a **second, distinct logged-in identity**) → `/recipes/search?q=...` → finds User A's recipe.

**Acceptance criteria:**
1. A logged-in user can initiate a Stripe-hosted Checkout redirect from `/pro`, correctly relaying `checkout_url` — verified via mocked-backend integration test (resolution 1).
2. A Pro-entitled user can author a recipe (title/instructions/servings + ≥1 catalog-sourced ingredient), see server-computed macro/micro totals (per-recipe and per-serving, `available`/`partial`/`unavailable` status per journey 1's established three-state pattern), and publish it.
3. A **second, distinct, also-Pro-entitled** user identity can find that published recipe via `/recipes/search`.
4. A non-Pro-entitled user attempting to publish or search receives a clear "Upgrade to Pro" prompt — `402`/`NOT_ENTITLED` is a first-class expected UI state, not a raw error.
5. Every new/changed typed API client module has a Zod schema matching the real backend Pydantic schema field-for-field.
6. TypeScript strict mode, zero `any`, unit/integration coverage on every new component/hook/schema; a new Playwright E2E spec covering the publish→search backbone with two distinct identities.
7. WCAG 2.1 AA baseline met, including the nutrient-totals table and the ingredient picker.
8. CI green for `frontend-ci.yml`.

**Explicitly out of scope:** `social-service`, `analytics-service`, `nutrition-assistant-service` chat, water/fasting/meal-planning, wearables, editing a recipe's published visibility rules, recipe images/media, any billing-service/recipe-service backend change, real Stripe test-mode key provisioning.

---

## 2. Architectural classification

Frontend-only change. Server Components by default, Client Components where interactive. `/pro`, `/recipes`, `/recipes/[recipeId]` are Server Component shells with client sub-parts; `/recipes/new` and `/recipes/search` are Client Components. Server state via TanStack Query. No new client-side store.

---

## 3. Files to create or modify

```
frontend/
  app/
    pro/page.tsx, pro/success/page.tsx, pro/cancel/page.tsx
    recipes/page.tsx, recipes/new/page.tsx, recipes/[recipeId]/page.tsx, recipes/search/page.tsx
    api/
      billing/checkout-sessions/route.ts
      recipes/route.ts, recipes/[recipeId]/route.ts, recipes/[recipeId]/publish/route.ts,
      recipes/[recipeId]/unpublish/route.ts, recipes/search/route.ts
  components/
    features/
      billing/UpgradeToProCard.tsx, CheckoutRedirectButton.tsx, ProSuccessBanner.tsx, ProCancelBanner.tsx
      recipes/RecipeForm.tsx, IngredientPicker.tsx, IngredientRow.tsx, RecipeNutrientTotals.tsx,
        RecipeCard.tsx, RecipeList.tsx, PublishRecipeButton.tsx, RecipeSearchBox.tsx, RecipeSearchResultList.tsx
      catalog/{ProductSearchBox,ProductResultList,ProductResultCard}.tsx  # MODIFY — mode: "log"|"select"
      AppNav.tsx                      # MODIFY — "Recipes" + "Upgrade to Pro" links
  lib/
    api/billing.ts, recipes.ts        # NEW — NOT_ENTITLED surfaced as a distinguishable typed error
    server/backend-config.ts          # MODIFY — BILLING_SERVICE_BASE_URL, RECIPE_SERVICE_BASE_URL,
                                       #   NEXT_PUBLIC_APP_BASE_URL (resolution 8)
    hooks/useCreateCheckoutSession.ts, useOwnRecipes.ts, useRecipe.ts, useCreateRecipe.ts,
      useUpdateRecipe.ts, usePublishRecipe.ts, useUnpublishRecipe.ts, useDeleteRecipe.ts, useSearchRecipes.ts
  schemas/billing.ts, recipe.ts
  messages/en.json                   # MODIFY
  tests/
    unit/schemas.billing.test.ts, schemas.recipe.test.ts, recipe-ingredient-mapping.test.ts
    integration/CheckoutRedirectButton.test.tsx, RecipeForm.test.tsx, IngredientPicker.test.tsx,
      PublishRecipeButton.test.tsx, RecipeSearchBox.test.tsx, route-handlers.test.ts (MODIFY)
    fixtures/billing.fixtures.ts, recipe.fixtures.ts
    e2e/pro-upgrade-recipe-publish-search.spec.ts, seed/seed.ts (MODIFY), seed/constants.ts (MODIFY)

docker-compose.yml                   # MODIFY — BILLING_SERVICE_BASE_URL, RECIPE_SERVICE_BASE_URL,
                                       #   NEXT_PUBLIC_APP_BASE_URL + depends_on billing-service/recipe-service
infra/k8s/charts/frontend/
  values.yaml                        # MODIFY — 6th+7th downstreamEgress entries + env vars
  templates/networkpolicy-egress-downstream.yaml  # MODIFY — 2 more egress blocks
docs/api-catalog.md                  # MODIFY
```

No change to any `services/*` file. No new backend endpoint, no new domain event, no `infra/terraform` change.

---

## 4. API integration

**`lib/api/billing.ts`**: `createCheckoutSession({successUrl, cancelUrl, customerEmail?})` → `{stripeSessionId, checkoutUrl}` — a Stripe-hosted Checkout Session redirect (billing-service never collects card data). `409 SUBSCRIPTION_ALREADY_ACTIVE` is expected (already-Pro user) → redirect to `/recipes` with a message, not an error.

**`app/api/billing/checkout-sessions/route.ts`**: 401 if unauthenticated, builds absolute `success_url`/`cancel_url` from `NEXT_PUBLIC_APP_BASE_URL`, POSTs, relays verbatim.

**`lib/api/recipes.ts`**: full CRUD + publish/unpublish/search. Server computes all macro/micro totals (`recipe_nutrient_calculator.py`, independent local copy per recipe-service's "never caller-supplied macros" rule) — client never sends totals, only `{catalog_product_id, quantity_grams}` per ingredient. `RecipeResponse.computed_totals = {per_recipe, per_serving}`, each with `available|partial|unavailable` status — reuses journey 1's three-state degrade pattern.

**Error shape**: `NOT_ENTITLED` (402) surfaced as a distinguishable typed error so `PublishRecipeButton`/`RecipeSearchBox` branch on it specifically, per acceptance criterion 4.

**Entitlement propagation timing — resolved, no frontend polling needed.** `is_user_entitled` (used by both publish and search handlers) is cache-first, falling back to a synchronous call to `GET /internal/v1/billing/entitlements/{user_id}` on a cache miss — that endpoint reads billing-db directly, correct the instant the checkout webhook commits, independent of the async `EntitlementGranted` event's propagation delay. The frontend never needs to poll or wait; the existing cache-first/fallback-to-sync pattern already absorbs this.

---

## 5. Cross-service impact

First frontend consumer of `billing-service` and `recipe-service`, both already `active`, no backend code change required. `402`/`NOT_ENTITLED` is a first-class UI state. Recipe search is Pro-gated for the searching user too (see resolution 2). `billing-service` has no user-facing entitlement-status endpoint — only checkout-sessions is public; the internal entitlement-read endpoint must never be called by the frontend (see resolution 3). NetworkPolicy egress: same known, already-documented gap journeys 1-2 carry — adds a 6th/7th entry to that list, fixing the ingress side is `billing-agent`'s/`recipe-agent`'s own follow-up.

---

## 6. Accessibility & i18n

`RecipeNutrientTotals` reuses the `MicronutrientTable` status-aware accessible-table pattern. `IngredientPicker` reuses `ProductSearchBox`'s semantic list/keyboard operability in "select" mode. `PublishRecipeButton`/`RecipeSearchBox`'s 402 branches render explicit text CTAs, never color-only. `axe-core` on all seven new screens. Manual keyboard-only + screen-reader smoke pass before `/implementation-review`. Per CLAUDE.md §8: the publish action carries explicit copy that this makes the recipe visible to other users, a distinct consent surface.

---

## 7. Testing/CI/deploy

No change to `frontend-ci.yml`'s stage shape. 80% overall coverage threshold unchanged. `docker-compose.yml`/`infra/k8s/charts/frontend/` gain the new downstream service wiring, mirroring the existing pattern exactly.

**E2E seed infrastructure**: `seed.ts` extended to seed a second identity (finder) plus an `active` subscription row directly into billing-db for both users (`status='active'`, far-future `current_period_end`), bypassing Stripe/webhook entirely — same "seed the state directly" precedent as journey 1's pre-verified user, applied one level deeper.

---

## 8. Test plan reference

`/test-plan` defines concrete cases next: schema round-trips (including the three-state status unions); checkout-sessions Route Handler's 401/409/error cases; `PublishRecipeButton`/`RecipeSearchBox`'s 402 branches (MSW-mocked — the only deterministic way to exercise the entitlement gate); `IngredientPicker` select-mode wiring; axe-core; the two-identity Playwright E2E spec starting from seeded-Pro state for both users.

---

## 9. Risks and open questions — resolved at approval time (2026-09-11)

1. **Stripe checkout cannot be genuinely completed in this environment — RESOLVED, proceed as the agent proposed.** No test-mode Stripe keys exist anywhere in this stack (`docker-compose.yml`'s placeholders, already tracked as a lead-time item in billing-service's own plan) — this is an environmental constraint, not a design choice with real alternatives available here. The E2E spec does not exercise a live Stripe round-trip: both identities start from directly-seeded Pro state; the checkout-initiation leg (button → POST → redirect-URL handling, `/pro/success`/`/pro/cancel` rendering) is covered only by an MSW-mocked integration test. A true checkout E2E stays blocked until a real Stripe test-mode account is provisioned — tracked as a `devops-agent`/`billing-agent` follow-up, not attempted here.
2. **Recipe search is Pro-gated for the searcher too, not just the publisher — PROCEED as designed, per recipe-service's already-shipped, already-reviewed contract.** This is existing backend product behavior (STATUS.md confirms it was a deliberate choice), not something this plan introduces or should relitigate. The UI must make this legible: a free user hitting `/recipes/search` sees a clear "Search is a Pro feature" prompt, not a confusing raw 402.
3. **No user-facing "am I Pro?" endpoint — RESOLVED, proceed as the agent proposed.** No reliable client-side "Pro badge" is possible with today's backend surface. "Upgrade to Pro" CTAs show unconditionally, even to already-Pro users (who get a `409`→redirect on click); the actual gate is discovered by attempting publish/search and handling `402` gracefully — same honesty-over-false-confidence posture journey 2 used for degraded AI states. A real nav indicator needs a new public billing-service endpoint — `billing-agent`-owned, out of scope here.
4. **Two-user E2E testing infrastructure — proceed as designed.** Confirmed no app-code change needed (session state already correctly scoped per browser cookie jar via `lib/session.ts`'s design) — only the test itself needs a second `browser.newContext()` and a second seeded identity. `qa-agent` to confirm `playwright.config.ts`'s single-worker setup remains adequate with two cookie jars alive in one spec.
5. **Ingredient-picker reuses `ProductSearchBox`/`ProductResultList`/`ProductResultCard`** via a `mode: "log"|"select"` prop, same generalization pattern journey 2 used for `aiContext`. Revisit only if this makes those three components unwieldy across three call sites.
6. **Zero-ingredient recipes are technically backend-valid — PROCEED with a frontend-only UX guard** requiring ≥1 ingredient before enabling submit, documented explicitly as a UI-layer opinion, not an assumed backend contract.
7. **Edit-after-publish behavior — RESOLVE EMPIRICALLY during Stage B, not assumed here.** The implementing agent must read `recipe-service`'s actual `update_recipe.py` to confirm whether editing an already-published recipe is blocked or silently changes what's already cross-user-searchable, before writing any edit-after-publish test case — report the actual behavior found, don't guess.
8. **New env-var direction — RESOLVED: `NEXT_PUBLIC_APP_BASE_URL`.** The checkout Route Handler needs this app's own public base URL to build absolute `success_url`/`cancel_url` — the first downstream env var pointing at the frontend itself rather than outward at a backend. Named `NEXT_PUBLIC_APP_BASE_URL` (matches Next.js's public-env-var convention), defaulting to `http://localhost:3000` in `docker-compose.yml`.
9. **No feature flag this pass — proceed as designed.** Consistent with journeys 1-2's reasoning. A kill-switch flag around the checkout button is named as a candidate follow-up once real Stripe keys exist and `security-agent` weighs in — not built now.
