# ADR-0021: Scale North Star and Revisit Triggers

## Status
Accepted

## Date
2026-08-23

## Context
A long-term throughput/scale ambition (the kind of number that would force
real re-architecture: sharding, multi-region, moving off a shared broker)
is easy to lose track of in a spec that otherwise, correctly, defers
infrastructure decisions until measured need (ADR-0012's pattern, applied
throughout this repo). Without writing the ambition down, it either gets
forgotten (v1 architecture accidentally becomes permanent) or it leaks
into v1 as premature over-engineering (building for a scale that may
never arrive, at the cost of shipping speed now). This ADR exists to hold
both of those failure modes off at once: state the ambition explicitly,
but gate every scale-driven architecture change behind a measured
trigger, never a guess.

## Decision
- **State the target explicitly**: no specific scale target beyond
  standard production reliability. NutriApp is an early-stage product with
  no committed growth target; this is a deliberate, explicit answer, not a
  gap — it will be revisited once real usage data exists to set one
  meaningfully.
- **v1 is built for correctness and moderate scale, not the north star.**
  Every architectural choice elsewhere in this repo (hexagonal, CQRS
  only where read/write asymmetry justifies it, RabbitMQ over Kafka,
  Postgres full-text search over OpenSearch, EKS without a service mesh)
  already reflects this — this ADR does not change any of them. It only
  makes explicit which measured signal would.
- **Define concrete revisit triggers per likely bottleneck**, not a
  single aggregate number (aggregate throughput targets don't tell an
  agent which specific service or pattern to change). Examples, to be
  replaced with your domain's actual services and thresholds:
  - `diary-service` write QPS exceeds 200 sustained writes/sec (a
    conservative single-node Postgres write ceiling) -> revisit database
    sharding by `user_id`.
  - `catalog-service` read latency breaches its SLO under real load with
    Postgres full-text search already tuned -> the trigger already
    defined in ADR-0012 (OpenSearch activation) fires.
  - RabbitMQ consumer lag (`docs/observability-slo.md` SLIs) breaches
    target sustained, not just during a traffic spike -> revisit the
    Kafka fallback already documented in ADR-0004.
  - A single-region deployment's latency to a significant user
    population exceeds an acceptable bound, or a regulatory data-
    residency requirement appears (see `docs/multi-region-strategy.md`)
    -> revisit multi-region topology.
  - `nutrition-assistant-service`/`food-recognition-service` per-request LLM/vision
    cost, multiplied by realistic growth, threatens unit economics
    (`docs/cost-management.md`) -> revisit model tier
    (`.claude/skills/llm-cost-and-model-selection/SKILL.md`) or a
    self-hosted model before revisiting infrastructure.
- **Every trigger above is measured, not assumed** — the same discipline
  ADR-0012 already applies to catalog search extends to every scale
  decision in this repo. A trigger firing means "open a new ADR
  evaluating the change," not "implement the change automatically."

## Considered Alternatives
- **No explicit north star, decide scale architecture reactively as
  problems appear** — closest to this repo's general bias toward
  deferring infrastructure, but risks losing the ambition entirely (no
  record of what "large scale" was even supposed to mean for this
  product) and risks an agent being asked to "design for massive scale"
  with no shared definition of what that means, leading to inconsistent
  over-engineering in some services and under-engineering in others.
- **Design every service for the north star from v1** — rejected;
  directly contradicts the measured-need pattern used everywhere else in
  this repo (ADR-0012, ADR-0017, ADR-0004) and would slow initial
  development substantially for a scale that may be years away or never
  arrive.

## Consequences
### Positive
- The scale ambition survives in a durable, specific, checkable form
  instead of an unwritten assumption.
- v1 stays pragmatic — this ADR adds no new infrastructure by itself.

### Negative / Trade-offs
- Requires actually wiring the SLIs referenced above into
  `docs/observability-slo.md` dashboards so the triggers can be
  evaluated on real data, not guessed at during a review.

### Follow-up actions
- Add each trigger above as a tracked metric/alert threshold in
  `docs/observability-slo.md` once the relevant service exists.
- Review this ADR at the same cadence as the SLO review in
  `docs/observability-slo.md` section 6 (quarterly, or whenever a new
  service ships) — a north star set once at launch and never revisited
  has the same failure mode as an SLO treated the same way.

## References
- ADR-0004, ADR-0012, ADR-0017, ADR-0018
- `docs/observability-slo.md`
- `docs/cost-management.md`
- `docs/multi-region-strategy.md`
- `DOMAIN-SETUP.md` section 6
