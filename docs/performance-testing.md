# Performance & Load Testing

Complements the functional testing pyramid in `docs/testing-strategy.md`,
which deliberately does not cover load/performance. See
`.claude/skills/load-testing/SKILL.md` for the quick-reference version.

## 1. Tooling

**k6** (scriptable in JavaScript, good CI integration, native Prometheus
output) for HTTP load tests. **Locust** is an acceptable alternative for
scenarios needing complex Python-side logic (e.g. simulating realistic usage
patterns over a day) — pick one per test suite and stay consistent
within it, don't mix both for the same target.

## 2. What Gets Load Tested

Not everything — only paths where a performance regression would be a real
production incident:

| Endpoint / flow                          | Why it matters                                  | Target SLO (p95)     |
|---------------------------------------------|------------------------------------------------------|--------------------------|
| `POST /api/v1/auth/login`                       | First thing every session does; brute-force-adjacent    | < 300ms                    |
| `POST /api/v1/diary-entries` (core write action)                    | Highest-frequency write in the whole system                | < 250ms                    |
| `GET /api/v1/nutrition/summary` (read model)     | Read-heavy, hit on every app open                             | < 150ms (Redis-backed)        |
| `POST /api/v1/vision/analyze` (photo upload)              | Calls an external vision API — latency-sensitive AND cost-sensitive | < 3s (dominated by external call) |
| `POST /api/v1/chat` (RAG assistant)                          | Calls an external LLM — same concern as vision                        | < 5s (streamed response, TTFB < 1s) |
| Event consumer lag (`diary.food_entry.logged` -> read model updated) | Determines how stale the daily summary can appear                    | < 2s end-to-end                    |

## 3. Test Types

- **Load test**: sustained expected-peak traffic, verify SLOs hold, no error
  rate increase.
- **Stress test**: increase load past expected peak until something breaks,
  to know the actual ceiling and which dependency fails first (usually the
  external vision/LLM API or the database connection pool).
- **Soak test**: sustained moderate load over hours, to catch memory leaks,
  connection pool exhaustion, or slow degradation not visible in a short test.
- **Spike test**: sudden burst (e.g. a marketing push), verify autoscaling
  (HPA) reacts fast enough and the circuit breakers protect downstream
  external APIs from being hammered.

## 4. When Load Tests Run

- **Not on every PR** — too slow and resource-intensive for the fast-feedback
  CI loop.
- Run against `staging` (which mirrors prod topology at smaller scale, per
  `docs/terraform-and-infrastructure.md`) before any promotion to `prod` that
  touches a hot path in the table above.
- Scheduled soak test weekly against `staging` regardless of changes, to catch
  slow leaks introduced by any accumulated change.

## 5. Failure Policy

A load test that misses its SLO **blocks promotion to prod** for the change
under test — the same human-in-the-loop gate philosophy as the functional
test gates in CLAUDE.md section 6, applied to non-functional requirements.
The human decides whether to accept a documented, temporary SLO regression
(with a follow-up ticket) or hold the release.

## 6. External Dependency Cost Awareness

Because `food-recognition-service` and `nutrition-assistant-service` calls are billed per request
by third-party providers, load tests against those endpoints in `staging`
must use **sandboxed/mocked external endpoints** wherever the provider offers
one, or a strict, pre-agreed request budget if not — never run an
uncapped load test against a metered production third-party API.
