# Chaos Engineering

Full rationale: ADR-0016. This document is the working reference for
`infra-agent` and `qa-agent` when defining or reviewing an experiment.

## 1. Process (every experiment, no exceptions)

1. **Steady-state hypothesis** — a specific, measurable claim about normal
   behavior (e.g. "checkout p95 latency stays under 400ms").
2. **Blast radius** — which service(s), which `staging` resources
   specifically; never project-wide, never `prod`.
3. **Fault to inject** — one of: latency injection, connection throttling,
   pod termination, AZ failure simulation. One fault per experiment — never
   combine faults in a single run, since a combined failure makes it
   impossible to attribute which resilience pattern did or didn't hold.
4. **Abort condition** — an automatic stop tied to a real SLO
   (`docs/observability-slo.md`) being breached, not a manual "someone
   notices and stops it."
5. **Review** — the experiment definition goes through the same PR review
   as any other change (CLAUDE.md section 6) before it's scheduled.
6. **Run, observe, document** — record whether the hypothesis held; if it
   didn't, the resulting fix follows the normal implementation-plan pipeline
   like any other bug.

## 2. Experiment Catalog (add one row per experiment as they're built)

| Service              | Fault                          | Hypothesis                                   | Status  |
|------------------------|-----------------------------------|--------------------------------------------------|-----------|
| `identity-service`      | RDS connection throttling 50%    | Auth p95 stays under 400ms via circuit breaker fallback | Planned |

This table starts empty of real results by design — it fills in as each
service is scaffolded and its first experiment actually runs, per
`docs/project-status-tracking.md`'s "specification vs. actual state"
distinction.

## 3. What This Does Not Cover

- Load/stress/soak/spike testing (single-dimension: how much traffic can
  the system take) is a distinct concern — see
  `docs/performance-testing.md`.
- Security-focused fault injection (e.g. simulating a compromised
  credential) belongs to `security-agent` and `docs/incident-response.md`'s
  tabletop exercises, not this chaos-engineering process.
