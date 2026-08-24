# ADR-0019: Saga Pattern for Cross-Service Business Transactions

## Status
Accepted

## Date
2026-08-23

## Context
CLAUDE.md sections 2.3-2.4 (CQRS/Event Sourcing + Outbox) guarantee
consistency *within* a single service's write model and *reliable
delivery* of its published events. Neither addresses what happens when a
single business operation must succeed or fail as a unit **across
multiple services** — e.g. an operation that needs `diary-service` to
record an action, `nutrition-calculation-service` to update a derived value,
and `notification-service` to confirm it, where a failure partway through
must not leave the system in a state that looks successful to the user
but isn't. Without an explicit pattern, agents will be tempted to
reach for a distributed transaction (two-phase commit) across service
boundaries, which directly violates the "one database per service,
independently deployable" principle in CLAUDE.md section 2.2.

## Decision
- **No distributed transactions (2PC) across service boundaries, ever.**
  Every cross-service business transaction is a **Saga**: a sequence of
  local transactions, each in its owning service, coordinated either by
  choreography (each service reacts to the previous service's event) or
  orchestration (a dedicated saga orchestrator issues commands and
  tracks state).
- **Default to choreography** (services react to each other's domain
  events, already flowing through RabbitMQ per CLAUDE.md section 2.4) for
  sagas with 2-3 steps and no need for centralized visibility into
  in-flight state. This requires no new infrastructure — it is the
  existing event-driven architecture, used deliberately for a multi-step
  business transaction rather than independent projections.
- **Switch to orchestration** (a dedicated saga orchestrator — e.g. a
  lightweight component in `bff-service` or a new dedicated
  `saga-orchestrator-service` if the number of orchestrated sagas grows
  past a handful) once *any* of the following is true:
  - A saga has 4+ steps, making the "which service reacts to what" chain
    hard to trace across `docs/events-catalog.md` entries.
  - The product needs to show a user the live status of an in-progress
    multi-step operation (orchestration has a natural state machine to
    query; choreography does not, without adding one).
  - Two or more sagas need to share compensation logic.
- **Every saga step that can fail after a prior step succeeded must
  define an explicit compensating action** (e.g. "if step 3 fails,
  reverse step 1's effect via a `<Verb>Reversed` event"), documented
  alongside the saga definition, not left as an implicit assumption.
  A saga step with no defined compensation is treated as a design gap,
  not an acceptable simplification.
- **Idempotency and at-least-once delivery** (already mandatory per
  CLAUDE.md section 2.4) apply to every saga step — a saga step handler
  must be safe to receive its triggering event more than once.

## Considered Alternatives
- **Two-phase commit (2PC) / distributed transactions** — rejected
  outright: requires a shared transaction coordinator, blocks on the
  slowest participant, and is incompatible with "one database per
  service, independently deployable" (CLAUDE.md section 2.2). Not
  reconsidered regardless of future scale — this is a correctness/
  availability trade-off this project does not want, not a
  performance-driven deferral like other ADRs in this repo.
- **Orchestration from day one for every cross-service flow** — more
  observable and easier to reason about for complex sagas, but adds a
  stateful coordinator component and its own failure modes before most
  flows are complex enough to need it. Deferred per the activation
  triggers above, consistent with this project's general bias against
  infrastructure ahead of measured need (see ADR-0012, ADR-0017).

## Consequences
### Positive
- Cross-service business transactions have one documented pattern
  instead of being invented ad hoc per feature.
- Choreography reuses existing messaging infrastructure — zero new
  operational surface for the common case.

### Negative / Trade-offs
- Choreography-based sagas are harder to observe end-to-end than a
  single orchestrator's state machine — mitigated by requiring
  `correlation_id` propagation (already mandatory, CLAUDE.md section 2.8)
  across every event in a saga, so distributed tracing can reconstruct
  the flow even without a central coordinator.
- Compensating actions add real domain complexity (a `<Verb>Reversed`
  event is not automatic) — this is treated as inherent complexity of
  distributed business logic, not a shortcut to skip.

### Follow-up actions
- Add a "Sagas" section to `docs/events-catalog.md`'s format, listing
  each saga's steps, triggering events, and compensating actions
  alongside individual event definitions.
- `architecture-agent` reviews any new cross-service event chain for
  whether it constitutes an undocumented saga (2+ services, ordered
  steps, a business outcome that must be all-or-nothing) and requires it
  be documented per this ADR before merge.

## References
- CLAUDE.md sections 2.2, 2.3, 2.4, 2.8
- `docs/events-catalog.md`
- `.claude/skills/saga-conventions/SKILL.md`
