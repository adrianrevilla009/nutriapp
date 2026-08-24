---
description: Conventions for implementing cross-service business transactions (Sagas) via choreography or orchestration. Use whenever a change requires coordinating state across 2+ services as a single business outcome.
---

# Saga Conventions

Full rationale: ADR-0019. Living catalog of actual sagas:
`docs/sagas-and-distributed-transactions.md`. This skill is the
implementation checklist; the doc above is the specification of *which*
sagas exist.

## Before Implementing Any Cross-Service Flow

1. Check `docs/sagas-and-distributed-transactions.md` — is this flow
   already documented as a saga? If not and it involves 2+ services with
   an ordered, all-or-nothing outcome, it needs a new entry there
   **before** implementation, not after.
2. Never reach for a distributed transaction (2PC) across service
   boundaries — this is a hard rule per ADR-0019, not a default that can
   be overridden for convenience.
3. Decide choreography vs. orchestration using ADR-0019's activation
   triggers (step count, need for centralized status visibility, shared
   compensation logic) — don't default to orchestration just because it
   feels more explicit; choreography is the default for simple cases.

## Choreography Implementation Checklist
- Each step is a normal domain-event consumer, following the same
  idempotency requirement as any other consumer (CLAUDE.md section 2.4).
- `correlation_id` is set at the saga's first step and propagated through
  every subsequent event's metadata — this is what makes the saga
  traceable later without a central coordinator.
- Every step that can fail after a prior step succeeded has an explicit
  compensating event defined **before** the happy path is implemented,
  not added reactively after a production incident reveals the gap.

## Orchestration Implementation Checklist
- The orchestrator holds saga state explicitly (a state machine, not
  implicit control flow) — a saga instance's current step must be
  queryable, since that queryability is the reason orchestration was
  chosen over choreography.
- The orchestrator issues **commands** to each participating service
  (not events — commands express intent, per
  `.claude/skills/hexagonal-architecture/SKILL.md`) and reacts to their
  resulting events to advance the state machine.
- Compensation is driven by the orchestrator explicitly stepping
  backwards through already-completed steps, not by each service
  independently deciding to compensate — this is the main practical
  difference from choreography's compensation model.

## Testing Requirements
- Every saga has a test for the full happy path (every step succeeds).
- Every saga has a test per failure point (step N fails, verify the
  correct compensating action(s) fire and the system reaches a
  consistent end state, not a partially-applied one).
- Idempotency: replaying any single step's triggering event twice must
  not double-apply that step's effect — tested explicitly per step, not
  assumed from the general idempotency requirement.
- A saga's end-to-end test uses the real messaging infrastructure
  (`testcontainers` per `docs/testing-strategy.md`), not fully mocked
  event delivery, since the interaction between services is exactly what
  a saga test needs to verify.

## Rules
- A saga step's compensating action is itself a normal domain event,
  documented in `docs/events-catalog.md` like any other event — it does
  not get a special exemption from that documentation requirement just
  because it represents a "reversal."
- Never implement a saga step as a synchronous call chain across
  services "for simplicity" — this reintroduces the tight-coupling and
  availability-cascade problems the async event-driven architecture
  (CLAUDE.md section 2.2) exists to avoid.
- `architecture-agent` reviews every new saga entry in
  `docs/sagas-and-distributed-transactions.md` for a defined
  compensating action per step before approving the implementation plan.
