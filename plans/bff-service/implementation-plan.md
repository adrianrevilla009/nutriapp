# Implementation Plan — `bff-service`

**Status:** Approved
**Date approved:** 2026-08-29
**Stage:** 2 (Implementation Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Related:** ADR-0001 (hexagonal architecture), ADR-0002 (CQRS/ES scope — N/A, no persistence of business state), ADR-0008 (Kong + bff-service split), ADR-0022 (JWT/JWKS), `.claude/agents/bff-agent.md` (new this session), `.claude/skills/resilience-patterns/SKILL.md` (mandatory), `.claude/skills/api-conventions/SKILL.md`, `docs/api-catalog.md`, `docs/domain-glossary-and-context-map.md`, `services/diary-service/README.md`, `services/nutrition-calculation-service/README.md`

## 1. Scope

Build `bff-service` end-to-end: a thin aggregation layer, plus its Terraform/Helm/CI wiring, reusing the shared platform scaffolding. Unlike every prior service, this one has **no database of its own for business state** and **publishes/consumes no domain events** — see §2.

**Bounded context** (ADR-0008, `.claude/agents/bff-agent.md`): frontend-facing response aggregation only. It sits behind Kong (edge concerns: TLS, rate limiting, JWT signature validation, CORS — Kong's job, not this service's) and composes responses for specific frontend screens by calling downstream domain services. It contains orchestration, never business logic — the single non-negotiable rule for this service, per ADR-0008's own stated reason for splitting it out from Kong in the first place.

**Architecture review (this session, `architecture-agent`, before this plan was written):** confirmed the MVP scope below — one aggregation endpoint, three parallel calls to already-public, already-merged endpoints, no downstream service needs a new endpoint.

**Acceptance criteria:**

1. **`GET /api/v1/bff/dashboard?date={date}`** — the authenticated user's home/dashboard screen, covering CLAUDE.md's E2E journey 1 ("register → log a food item from catalog search → see macro/micro totals"). Fans out **three parallel** calls:
   - `diary-service`: `GET /api/v1/diary/summary?date={date}` — today's logged totals (calories, macros, water, fasting windows ended).
   - `nutrition-calculation-service`: `GET /api/v1/nutrition/totals/{date}` — computed macro/micro nutrient totals.
   - `nutrition-calculation-service`: `GET /api/v1/nutrition/target` — the active calorie/macro target.
   All three already validate the caller's JWT independently (ADR-0022, shared-contracts) — `bff-service` forwards the incoming request's `Authorization` header unchanged to each downstream call rather than re-deriving or re-signing anything.
2. **Per-call resilience**, each of the three calls behind its own named circuit breaker + `tenacity` retry + explicit timeout + dedicated `httpx.AsyncClient` (`resilience-patterns/SKILL.md`). A failure or open circuit on any **one** call degrades only that section of the response — e.g. `{"diary_summary": {...}, "nutrient_totals": {"status": "unavailable"}, "target": {...}}` — never a `5xx` for the whole endpoint because one downstream dependency is unhealthy.
3. **Known upstream gap, must degrade gracefully, not fail loudly** (architecture-agent's finding): `nutrition-calculation-service`'s target endpoint has a documented gap — `Sex.OTHER` users never get a computed target, and `ProfileRevealClient` failures defer recompute rather than erroring, so a `404`/empty-target response from that endpoint is an **expected**, not exceptional, case. `bff-service`'s target-section mapping must treat "no target exists yet" as `{"status": "unavailable"}`, distinct from "the call itself failed" (`{"status": "unavailable", "reason": "downstream_error"}` vs. `{"status": "unavailable", "reason": "not_yet_computed"}`) — never synthesize a value for either case.
4. **No business logic**: this service performs zero computation beyond structural reshaping (renaming/nesting the three downstream payloads into one response envelope). If implementation reveals a need for any new computed value, that value is added to the owning domain service's own API in a separate, properly-scoped change — never inlined here.
5. Coverage: domain ≥ 90% (expected to land near 100% given how thin this layer is), application ≥ 85%, infrastructure ≥ 70% (CLAUDE.md §3).
6. `docs/api-catalog.md` and `docs/domain-glossary-and-context-map.md` updated: three new synchronous-call relationships (`bff-service` → `diary-service`, `bff-service` → `nutrition-calculation-service` ×2), classified as **Open Host Service / Customer-Supplier via already-public API**, not a new internal-endpoint exception (distinct from the `profile-service`/`catalog-service`/`identity-service` internal-reveal precedents — these three calls hit ordinary public, Kong-routable endpoints, just called server-to-server here).

**Explicitly out of scope for this plan:**
- Any second aggregation endpoint — deliberately scoped to one, as a clean reference implementation of the pattern (architecture-agent's explicit guidance: "this is meant to be a thin reference implementation... not an attempt to cover every screen").
- Any aggregation touching `analytics-service`/`billing-service`/`social-service`/`recipe-service`/`activity-service` (Phase 2, don't exist).
- Kong's own declarative config (`infra/k8s/kong/kong.yaml`) — ADR-0008's own follow-up action, tracked separately, not part of this service's own implementation.
- Any caching layer of `bff-service`'s own — each downstream call already has its own cache-aside layer (diary-service's Redis cache, nutrition-calculation-service's caches); double-caching the same data here would be redundant staleness risk for no benefit at this scale.

## 2. Architectural classification

**Not applicable in the usual sense** (ADR-0002 scope is about services with meaningful persisted state — this service has none). No event sourcing, no CQRS, no owned write/read model. Domain layer is intentionally minimal: at most a couple of pure mapping/reshaping functions and the per-section "unavailable" status value object — no entities, no aggregates. Application layer: one query handler (`GetDashboardHandler`) that fans out the three calls and assembles the response. Infrastructure layer: the three downstream HTTP clients (each its own port/adapter), the one public route, composition root.

## 3. Files to create or modify

```
services/bff-service/
  pyproject.toml, uv.lock, Dockerfile, .dockerignore, README.md, CLAUDE.md
  domain/
    value_objects/       # SectionStatus (available | unavailable), with the two
                          # unavailable reasons from acceptance criterion 3
  application/
    queries/              # get_dashboard.py -- GetDashboardHandler, fans out
                          # the three calls via asyncio.gather, assembles the
                          # response, applies the per-section fallback mapping
    dto/
    errors.py
  infrastructure/
    http/
      routes/              # dashboard_routes.py, health.py
      schemas/              # DashboardResponse and its three section shapes
      dependencies.py       # forwards the incoming Authorization header;
                          # does NOT re-validate the JWT itself (Kong already
                          # will in a real deployment; for direct/dev calls,
                          # a lightweight signature check reusing
                          # shared-contracts' existing JWT dependency, purely
                          # to get user-facing 401s in local/dev without Kong
                          # in front -- never re-implements JWT verification
                          # logic of its own)
      error_mapping.py
    external/
      diary_service_client.py                # implements DiarySummaryPort
      nutrition_calculation_service_client.py # implements NutritionTotalsPort
                                              # and NutritionTargetPort (two
                                              # methods, two independently
                                              # named circuit breakers even
                                              # though it's one client class --
                                              # per resilience-patterns/SKILL.md's
                                              # "never share one breaker across
                                              # unrelated dependencies," these
                                              # two calls have unrelated failure
                                              # modes despite sharing a host)
    composition_root.py, main.py
  tests/
    unit/domain/            # SectionStatus value object
    unit/application/        # GetDashboardHandler: all-succeed, each single-call-
                          # failure case (3 of them), all-fail, the two
                          # "target unavailable" reason branches
    integration/infrastructure/  # each client against a fixture HTTP server,
                          # full circuit-breaker open/fallback/recovery matrix
                          # per client (3 independently named breakers total)
    contract/http/         # /api/v1/bff/dashboard response shape,
                          # degraded-section shape per dependency

infra/terraform/environments/dev/bff-service.tf   # mirrors the pattern, but
    notably no RDS schema/user needed (no database) -- ECR repo, IAM for
    whatever minimal secrets exist (none anticipated beyond standard
    service-to-service networking), narrower than every prior service's .tf
infra/k8s/charts/bff-service/     # own chart, correct env-list format +
    envFrom wiring from the start (same bar notification-service set) --
    no PVC/StatefulSet needed (fully stateless), no ExternalSecret needed
    unless a downstream-call credential turns out to be required (none
    anticipated -- these are ordinary public endpoints, not internal ones)
.github/workflows/bff-service-ci.yml   # mirrors the other services' pipelines
    minus the DB-dependent steps that don't apply here (no migration step,
    no DB-provision job in the chart)

docs/api-catalog.md                # add GET /api/v1/bff/dashboard (public,
    behind Kong), and note the three server-to-server calls it makes
docs/domain-glossary-and-context-map.md   # add bff-service's three
    Customer-Supplier relationships (see §6)
ARCHITECTURE.md                    # verify bff-service's existing
    description as "single entry point... routing, auth token validation,
    and request aggregation" is corrected per ADR-0008's own split --
    Kong owns routing/auth-token-validation, bff-service owns only
    aggregation; fix if ARCHITECTURE.md still conflates them (ADR-0008
    §Context flagged this exact conflation as the reason for the split)
docker-compose.yml                 # add a bff-service block (no bff-db --
    no database)
```

## 4. Ports/adapters affected

**New ports** (all introduced by this service): `DiarySummaryPort`, `NutritionTotalsPort`, `NutritionTargetPort` — three thin HTTP-client ports, each with a single method. No existing port from another service is reused. `packages/shared-contracts`' centralized JWT dependency may be reused for the lightweight local/dev 401 path per §3's dependencies.py note, following `food-recognition-service`'s and `notification-service`'s precedent.

No port from this service is called by anything else — `bff-service` is a pure caller, never a callee for any other backend service (only the frontend, via Kong, calls it).

## 5. Domain events

**None.** No event is published or consumed by this service (§1/§2) — nothing to add to `docs/events-catalog.md`.

## 6. Cross-service impact

**Flagged for `architecture-agent` review, already addressed this session:** three new synchronous call relationships, all against already-public, already-merged endpoints — no producer-side change required anywhere. Classify in `docs/domain-glossary-and-context-map.md` as **Open Host Service / Customer-Supplier**, explicitly distinct from the internal-reveal-endpoint exception pattern used by `profile-service`→`nutrition-calculation-service`, `catalog-service`→`food-recognition-service`, and `identity-service`→`notification-service`: those three exist specifically because the data needed wasn't safely exposable on a public endpoint (encrypted biometric data, an internal barcode lookup, a raw token secret). Here, the three calls hit the same public API surface the frontend itself would otherwise call directly — `bff-service` is simply doing the fan-out and composition the frontend would otherwise have to do in three separate requests.

No other service's code, contract, or behavior changes as a result of this plan.

## 7. Resilience/caching/migration needs

- **Circuit breakers**: three independently named instances (`diary_summary`, `nutrition_totals`, `nutrition_target`) — the two `nutrition-calculation-service` calls get separate breakers despite sharing a host, per `resilience-patterns/SKILL.md`'s "never share one breaker across unrelated dependencies" (their failure modes are unrelated — one can be down while the other is healthy).
- **Retry**: `tenacity` exponential backoff + jitter on all three; all three are GET/idempotent, so retry is unconditionally safe (no dedup-key concern, unlike a write).
- **Timeout**: explicit per-call timeout on all three, tuned tighter than a typical write-path call since this is a synchronous, user-waiting dashboard load — document the chosen values in `README.md` once implemented.
- **Bulkhead**: a dedicated `httpx.AsyncClient` per downstream service (2 clients: one for `diary-service`, one for `nutrition-calculation-service`, since the latter's two calls can share a connection pool to the same host while still using separate circuit breakers).
- **No caching layer of this service's own** (§1) — each downstream already caches; this service always makes a live call.
- **No migration** — no database.

## 8. Test plan reference

`/test-plan` will define concrete test cases next: `GetDashboardHandler`'s all-succeed / each-single-failure (×3) / all-fail / both target-unavailable-reason branches, the three clients' circuit-breaker open/fallback/recovery matrices, and contract tests for the full and each degraded response shape. Not enumerated further here.

## 9. Risks and open questions

1. **`ARCHITECTURE.md`'s stale description** (§3) — flagged as a probable pre-existing drift (ADR-0008 itself calls out this exact conflation as its reason for existing), to be corrected as part of this plan's own doc updates, not a separate follow-up.
2. **Local/dev JWT handling without Kong in front** (§3, `dependencies.py`) — a narrow, documented convenience for running this service directly in `docker-compose` during development, not a re-implementation of JWT verification; flagged so a reviewer doesn't mistake it for this service quietly taking on an edge-gateway responsibility that belongs to Kong.
3. No other open questions — the one architecturally significant question (which endpoint(s), which downstream calls) was resolved by `architecture-agent` before this plan was written (§1).
