# Implementation Plan — `frontend` (first cut: scaffold + E2E journey 1)

**Stage:** 2 (Implementation Plan) of the human-in-the-loop pipeline, CLAUDE.md §6.
**Approved:** 2026-09-08, by adrianrg1996@gmail.com.

**Related:** CLAUDE.md §2.2 (Kong + `bff-service`), §3 (testing strategy, E2E journey 1), §4 (tech stack), §6 (pipeline), §7 (guardrails); `docs/frontend-architecture.md` (full spec); ADR-0008 (Kong + bff-service split); ADR-0022 (RS256/JWKS token scheme); `docs/authorization-model.md`; `docs/api-catalog.md`; `docs/containerization-and-orchestration.md`; `docs/ci-cd-strategy.md`; `.claude/skills/accessibility-standards`, `i18n-conventions`, `monorepo-tooling`, `feature-flags`, `testing-strategy`, `api-conventions/SKILL.md`. First-ever frontend code in this repo — no frontend precedent to mirror.

---

## 1. Scope

Build the frontend workspace scaffold plus exactly CLAUDE.md §3's E2E journey 1: **"Register → log a food item from catalog search → see macro/micro totals."** Everything else in `docs/frontend-architecture.md` (chat UI, recipes, social, photo/barcode logging, water/fasting/meal-planning, wearables, Pro-gating UI) is explicitly out of scope — same "ship a working first cut, defer the rest" pattern used by every backend service's own plan.

**Concrete routes (Next.js App Router, `frontend/app/`):**

| Route | Purpose | Calls |
|---|---|---|
| `/register` | Registration form | `POST /api/v1/auth/register` (identity-service) |
| `/verify-email` | Email-link landing page, reads `?reference_id=&secret=` | `POST /api/v1/auth/verify-email` (identity-service) |
| `/login` | Login form | `POST /api/v1/auth/login` (identity-service) |
| `/search` | Catalog product search | `GET /api/v1/catalog/products/search` (catalog-service) |
| `/log/[productId]` | Log a searched product | `GET /api/v1/catalog/products/{id}` + `POST /api/v1/diary/food-entries` |
| `/dashboard` | Macro/micro totals for a date | `GET /api/v1/bff/dashboard?date=` (bff-service) |
| `/` | Redirects based on session presence | none (middleware only) |

**Acceptance criteria:**
1. A new (pre-verified, per resolution 2 below) user can `/login` → `/search` → open `/log/[productId]` → submit a food entry → see `/dashboard` reflect updated totals, allowing for diary-service's documented eventual-consistency lag (§5).
2. Every typed API client module (`lib/api/identity.ts`, `catalog.ts`, `diary.ts`, `bff.ts`) has a Zod schema for every request/response shape, matching the real backend Pydantic schema field-for-field.
3. TypeScript strict mode, zero `any` in `lib/api/`, `schemas/`, `components/features/`.
4. Unit + integration coverage on every new component/hook/schema; one Playwright E2E spec exercising the journey (starting from a pre-verified seeded user, per resolution 2).
5. WCAG 2.1 AA baseline met for all six screens.
6. CI pipeline (lint → type-check → unit → integration → coverage-gate → build-image) green for `frontend-ci.yml`.

**Explicitly out of scope:** photo/barcode logging, chat, recipes, social, billing/Pro-gating UI, water/fasting/meal-planning screens, wearables, unit-preference (imperial) UI, dark-mode toggle beyond required theme-aware tokens, any elaborate design-token/component library (no `.claude/skills/frontend-design` exists in this repo — see resolution 1), any Kong/edge wiring, standing up a real mail-catcher (see resolution 2).

---

## 2. Architectural classification

Per `docs/frontend-architecture.md` §§1–3: Server Components by default, Client Components only where interactive (all four form/search/log screens are client components; `/dashboard` is a server component shell with a client refresh affordance). Server state: TanStack Query exclusively for all four backend calls. Client-only UI state: local `useState` — no Zustand needed for this narrow scope (the only cross-component state, session presence, is handled via a TanStack-Query-backed `useSession()` hook). No Redux.

---

## 3. Files to create or modify

```
frontend/
  package.json, tsconfig.json (strict: true), next.config.ts, .eslintrc.json,
  .prettierrc, vitest.config.ts, playwright.config.ts, Dockerfile, .dockerignore
  middleware.ts
  app/
    layout.tsx, page.tsx
    register/page.tsx, verify-email/page.tsx, login/page.tsx
    search/page.tsx, log/[productId]/page.tsx, dashboard/page.tsx
    api/
      auth/route.ts              # Route Handler proxy for identity-service
      catalog/route.ts            # Route Handler proxy for catalog-service (resolution 1)
      diary/route.ts              # Route Handler proxy for diary-service (resolution 1)
      bff/route.ts                # Route Handler proxy for bff-service (resolution 1)
  components/
    ui/                          # Button, TextField, Select, DatePicker, ErrorBanner, LoadingSkeleton
    features/
      auth/RegisterForm.tsx, VerifyEmailStatus.tsx, LoginForm.tsx
      catalog/ProductSearchBox.tsx, ProductResultList.tsx, ProductResultCard.tsx
      diary/LogFoodEntryForm.tsx
      dashboard/MacroTotalsCard.tsx, MicronutrientTable.tsx, TargetComparison.tsx
  lib/
    api/
      identity.ts, catalog.ts, diary.ts, bff.ts, http-client.ts
    hooks/
      useSession.ts, useSearchProducts.ts, useLogFoodEntry.ts, useDashboard.ts
    stores/                      # empty/reserved, no Zustand store needed
  schemas/
    identity.ts, catalog.ts, diary.ts, bff.ts
  tests/
    unit/, integration/, e2e/register-log-dashboard.spec.ts

infra/k8s/charts/frontend/
infra/terraform/environments/dev/frontend.tf
.github/workflows/frontend-ci.yml
docker-compose.yml   # new frontend service entry
pnpm-workspace.yaml   # first JS workspace root file
docs/api-catalog.md   # note frontend as a new caller of existing active rows
```

No change to any `services/*` file. No new backend endpoint. No new domain event.

---

## 4. API integration

**`lib/api/identity.ts`**: `register`, `verifyEmail`, `login` (generic error for wrong password / unverified email / locked account — the login form's copy must stay generic, the API gives no way to distinguish), `refresh`.

**`lib/api/catalog.ts`**: `searchProducts`, `getProductById` — both unauthenticated at the API level, but the frontend still gates `/search` behind a session for flow coherence.

**`lib/api/diary.ts`**: `logFoodEntry` — authenticated. Grounded semantics: `unit` is fixed to `"g"` this pass (no serving-size UI); the selected product's `nutrition_per_100g` is copied into `macros_per_unit` unchanged; `source.source_type = "catalog_product"`, `source.source_reference_id = product.product_id`. Micronutrients are not sent by this call — nutrition-calculation-service joins them separately.

**`lib/api/bff.ts`**: `getDashboard(date)` — authenticated. Response is three independent envelopes (`diary_summary`, `nutrient_totals`, `target`), each `{status, reason, data}` — the UI renders each section independently and shows its own degraded state when `status === "unavailable"`, never treats a 200 as "all data present."

**Authentication/session strategy**: a Next.js Route Handler (`app/api/auth/route.ts`) is the only thing that ever holds a raw token — proxies register/login/refresh/logout to identity-service, sets the refresh token as an `httpOnly`/`secure`/`sameSite=lax` cookie; the access token is held in memory only via `useSession()`, never `localStorage`. Per resolution 1 below, the other three services' calls are proxied the same way (`app/api/catalog/route.ts`, `app/api/diary/route.ts`, `app/api/bff/route.ts`), so the browser only ever talks to the Next.js server, never directly to any backend service.

---

## 5. Cross-service/cross-boundary impact

No backend code changes required for the endpoints called — all four surfaces are already `active` in `docs/api-catalog.md`. `bff-service`'s dashboard fan-out is asynchronous relative to a just-completed diary write (diary-service is fully event-sourced, async-projector-via-broker) — a user who logs a food entry and immediately navigates to `/dashboard` may see stale totals for a short, unbounded window. This is diary-service's documented, accepted design, not a bug — the frontend handles it visibly: the log-success screen says "logged — your dashboard may take a moment to update," and the dashboard offers a manual refetch, not just a background `staleTime` refresh.

---

## 6. Accessibility & i18n

WCAG 2.1 AA baseline (`.claude/skills/accessibility-standards/SKILL.md`) across all six screens: every input has a real associated `<label>`, inline errors tied via `aria-describedby`, full keyboard operability, visible focus rings. `/search`'s result list is semantic (`<ul>`/`<li>`), each "Log" action has an accessible name including the product name. `/dashboard`'s micronutrient breakdown renders as an actual accessible `<table>` (`MicronutrientTable.tsx`), not a chart-only view (no charting library introduced this pass). Unavailable-section states are conveyed via text, not color alone. `axe-core` runs in the integration suite against all six screens; critical/serious violations block merge. A manual keyboard-only smoke pass over the full journey happens before `/implementation-review`.

`next-intl` wired from the start with a single `en` locale — every user-facing string goes through it. All numeric/date formatting uses `Intl`/`next-intl`'s locale-aware formatters. Grams is the only unit surfaced this pass, consistent with §1's scope.

---

## 7. Testing/CI/deploy

CI (`frontend-ci.yml`) mirrors the backend stage order with JS-toolchain equivalents: `eslint`/`prettier --check` (lint), `tsc --noEmit --strict` (type-check), `gitleaks-action` (secret-scan, unchanged), `vitest run tests/unit`, `pnpm audit` (dep-vuln-scan), `vitest run tests/integration` (Testing Library + MSW — no separate contract stage; schema-mirroring accuracy is enforced by the Zod schemas + MSW fixtures built from real backend shapes), `vitest --coverage` against an 80% overall threshold (resolution 3 below), `docker build` + Trivy scan, `helm-lint-and-template` (new `infra/k8s/charts/frontend/` on `_lib/`, no DB/broker section), and a Playwright E2E stage against a full `docker-compose up` stack (resolution 2 below resolves how the seeded user is set up).

`docker-compose.yml`: new `frontend` service entry, repo-root build context, depends on `identity-service`/`catalog-service`/`diary-service`/`bff-service`. `infra/k8s/charts/frontend/`: new chart on `_lib/`, standard Deployment/Service/HPA/PDB/NetworkPolicy/ServiceAccount, no new resource class.

---

## 8. Test plan reference

`/test-plan` defines concrete cases next: Zod schema round-trip tests against real-shaped fixtures; MSW-mocked component tests for every documented error/edge shape (401, the dashboard's three `unavailable` envelopes, empty search results, diary-service 4xx validation); the axe-core pass; the Playwright E2E spec starting from a seeded pre-verified user.

---

## 9. Risks and open questions — resolved at approval time (2026-09-08)

1. **CORS/edge-routing — RESOLVED: proxy all four services through Next.js Route Handlers.** No backend code change. All browser-facing calls (`identity`, `catalog`, `diary`, `bff`) go through `app/api/*/route.ts` proxies, keeping this initiative entirely contained in `frontend/`. Flagged for `architecture-agent`: confirm this doesn't quietly duplicate what Kong is eventually meant to do (ADR-0008) — revisit once Kong is actually running in this environment.
2. **E2E verification gap — RESOLVED: seed a pre-verified test user.** The Playwright E2E spec starts from a fixture/seed user already marked verified (direct DB seed, test-only), skipping the real email-verification path. The `/verify-email` screen's own logic is still tested in isolation via MSW-mocked integration tests, not exercised in the full E2E run. Standing up a real mail-catcher (e.g. Mailpit-style) remains a legitimate future `devops-agent` follow-up, out of scope here.
3. **No design system/visual-identity convention exists — PROCEED with a minimal default.** No `.claude/skills/frontend-design` exists in this repo. `components/ui/` ships a minimal, unstyled-but-accessible set (semantic HTML, system font stack, WCAG-AA-contrast default colors) sufficient for journey 1. Any real visual identity/branding decision is deferred to a human call or a future `design` pass.
4. **Token storage strategy — PROCEED with the stated default, flagged for review.** In-memory access token + httpOnly-cookie refresh token, consistent with ADR-0022's revocation model. Not yet reviewed by `security-agent` — recommend that review happen during `/implementation-execution`, not after.
5. **Coverage threshold — RESOLVED: 80% overall.** No domain/application/infrastructure split exists in a frontend codebase to apply CLAUDE.md §3's per-layer targets to. A single 80% threshold applies across `lib/`, `schemas/`, `components/features/`. Revisit with `qa-agent` if this proves too loose or too strict once real coverage numbers exist.
6. **First JS/TS workspace in the monorepo.** `pnpm-workspace.yaml` is added as part of this scaffold, per `.claude/skills/monorepo-tooling/SKILL.md`'s already-decided "Frontend: pnpm workspaces" convention — no separate initiative needed.
7. **No feature flag introduced for journey 1 itself** — it is the flagship first feature, not risky/incomplete UI, per `.claude/skills/feature-flags/SKILL.md`'s "every flag needs a stated removal plan" framing. Deliberate choice, not a silent omission.
