# ADR-0016: Chaos Engineering in `staging`

## Status
Accepted

## Date
2026-08-23

## Context
CLAUDE.md section 2.6 mandates circuit breakers, retries, timeouts, and
bulkheads for every synchronous inter-service and external call. All of
this is currently verified only via unit tests that **mock** the failure
(a test asserts the circuit breaker trips when the mock raises an
exception N times) — which proves the code path exists, not that it
behaves correctly when a real dependency is actually slow, actually
returns malformed data, or actually disappears mid-request in a running
`staging` environment with real network behavior, real connection pools,
and real timeout interactions across services.

## Decision
Introduce scheduled, scoped chaos experiments against `staging` (never
`prod`), using **AWS Fault Injection Simulator (FIS)** — chosen for
native EKS/RDS/ElastiCache fault-injection actions and no new
infrastructure to operate, consistent with the AWS-native stack (ADR-0006).
- Experiments are defined per-service, not project-wide, and reviewed as
  code (same PR process as anything else) before being scheduled.
- Every experiment has a pre-declared **steady-state hypothesis**
  ("checkout latency p95 stays under Xms when RDS connections are
  throttled by 50%") and a **blast radius** limited to `staging`, with an
  automatic abort condition if a real SLO (per
  `docs/observability-slo.md`) is breached during the run.
- Experiments run on a schedule (initially monthly, per service, once that
  service exists), never ad hoc against a live `staging` deploy someone is
  actively using for manual testing.

## Considered Alternatives
- **Chaos Monkey / Chaos Toolkit (open source, self-hosted)** — more
  flexible and cloud-agnostic, but requires operating another tool;
  rejected in favor of the already-available AWS-native FIS given the
  project's single-cloud posture (ADR-0006), revisit if the project ever
  becomes multi-cloud.
- **No chaos testing, rely on resilience-pattern unit tests alone** — what
  exists today. Rejected per the Context above: a mocked circuit breaker
  test cannot catch real timeout/retry interaction bugs (e.g. two layers
  of retry compounding into a retry storm) that only appear under real
  network conditions.
- **Running experiments in `prod`** — the industry-standard advanced
  practice (real user traffic surfaces real failure modes `staging` never
  will), but rejected for this project's current maturity level; revisit
  once `staging` experiments have run cleanly for a sustained period and
  the team has confidence in abort tooling.

## Consequences
### Positive
- Resilience patterns are verified against real infrastructure behavior,
  not just mocks.
- Failure modes are discovered on a schedule, by the team, instead of
  during a real incident.

### Negative / Trade-offs
- `staging` becomes periodically degraded-by-design during an experiment
  window — anyone using it for manual QA at that moment needs to know an
  experiment is running (announced per
  `docs/environments-and-promotion.md`'s existing `staging` conventions).
- FIS experiment definitions are one more artifact to maintain per
  service, reviewed and versioned like test code.

### Follow-up actions
- Add the first FIS experiment (RDS connection throttling against
  `identity-service`, the reference implementation per CLAUDE.md section
  14) once that service exists in `staging`.
- Add experiment scheduling and abort-condition wiring to
  `docs/observability-slo.md`'s alerting so a breached SLO during an
  experiment pages the same way a real incident would (rehearsing the
  actual on-call path, per `docs/incident-response.md`).

## References
- `docs/chaos-engineering.md`
- CLAUDE.md section 2.6
- `docs/observability-slo.md`
