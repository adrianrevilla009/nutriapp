# Frontend Architecture

Expands the one-line mention in CLAUDE.md section 4 ("React + Next.js,
TypeScript strict mode, TanStack Query, Zod") into a full specification, at
the same rigor level as the backend's hexagonal layout.

## 1. Structure

```
frontend/
  app/                    # Next.js App Router: routes, layouts, server components
  components/
    ui/                     # Presentational, no business logic, storybook-documented
    features/               # Feature-scoped components (core-action, dashboard, chat)
  lib/
    api/                      # Typed API clients, one module per backend service,
                                #   generated/kept in sync with each service's OpenAPI spec
    hooks/                      # Shared React hooks
    stores/                       # Client-side state (see section 3)
  schemas/                        # Zod schemas mirroring backend Pydantic models
  tests/
    unit/                            # Vitest, component logic
    integration/                       # Testing Library, component + hook integration
    e2e/                                  # Playwright, critical journeys (mirrors
                                            #   docs/testing-strategy.md section 2.4)
```

## 2. Rendering Strategy

- **Server Components by default** (Next.js App Router) for anything that
  doesn't need interactivity — reduces client bundle size and moves data
  fetching closer to the BFF.
- **Client Components** only where interactivity is required (forms, the
  chat interface, charts) — marked explicitly with `"use client"`, never as a
  default.
- Data fetching for client components goes through **TanStack Query**,
  configured with sane defaults (staleTime tuned per data volatility — daily
  summary is more volatile than catalog data) and consistent error/loading
  states via shared hooks, not ad-hoc per component.

## 3. State Management

- **Server state** (anything from an API): TanStack Query — never duplicated
  into a separate client store.
- **Client-only UI state** (modal open/closed, form draft state, theme):
  local component state (`useState`/`useReducer`) by default; a lightweight
  store (Zustand) only when state genuinely needs to be shared across
  distant components without prop drilling.
- No Redux — unjustified complexity for this app's actual state shape.

## 4. Validation & Type Safety

- **Zod schemas** in `schemas/` mirror the backend's Pydantic models field-
  for-field. When a backend DTO changes, the corresponding Zod schema change
  ships in the same PR — checked by `architecture-agent` on cross-boundary
  changes.
- API clients in `lib/api/` are typed end-to-end: request/response types
  derived from the Zod schemas, never `any`.
- TypeScript strict mode (`strict: true`) repo-wide, no incremental opt-out
  per file without a documented reason.

## 5. Design System & Accessibility

- Shared design tokens (color, spacing, typography) — see
  `.claude/skills/frontend-design` conventions where applicable to this
  project's visual identity.
- **Accessibility is not optional**: semantic HTML first, ARIA only to fill
  genuine gaps, keyboard navigability for every interactive element,
  color-contrast checked against WCAG AA at minimum. `axe-core` runs as part
  of the component test suite, not just manually.
- Forms (the core action, especially) must be fully usable without a mouse —
  this is a daily-use app; friction compounds.

## 6. Internationalization

- All user-facing strings go through an i18n layer (`next-intl` or
  equivalent) from the start, even if only one locale ships at launch —
  retrofitting i18n later means re-touching every component.
- Units (grams vs. ounces, metric vs. imperial) are a first-class user
  preference, not hardcoded — domain data is meaningless if the unit is
  ambiguous or wrong for the user's region.

## 7. Testing

Mirrors the backend pyramid conceptually:
- Unit: pure functions, hooks in isolation (Vitest).
- Integration: component behavior with mocked API responses (Testing
  Library + MSW for network mocking).
- E2E: the same critical journeys from `docs/testing-strategy.md` section
  2.4, driven via Playwright against a full `docker-compose` stack.

## 8. Build & Deploy

- Static assets and server-rendered pages deploy as a containerized Next.js
  service (own Helm chart, per `docs/containerization-and-orchestration.md`),
  not a separate hosting platform — keeps the whole system deployable through
  one consistent pipeline (`docs/ci-cd-strategy.md`).
- Feature flags (`docs/feature-flags.md`) gate incomplete UI the same way
  they gate incomplete backend behavior.
