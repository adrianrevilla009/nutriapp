# Incident Response

A lightweight runbook appropriate for a solo-maintained, AI-agent-assisted
production system — the goal is a repeatable process, not enterprise
ceremony.

## 1. Severity Levels

| Severity | Definition                                                        | Example                                             |
|-----------|----------------------------------------------------------------------|----------------------------------------------------------|
| SEV-1       | User-facing outage or data-integrity risk affecting all/most users        | Event store unreachable; auth completely down                |
| SEV-2       | Partial degradation, a subset of users or one non-critical feature affected | `food-recognition-service` failing over to degraded mode; one region slow |
| SEV-3       | No user-facing impact, but a real problem (error budget burn, near-miss)     | Elevated error rate caught by alerting before user complaints |

## 2. Response Steps

1. **Detect** — via alerting (`docs/observability-slo.md`) or user report.
2. **Triage** — assign severity, open an incident record (a simple dated
   entry, e.g. `docs/incidents/YYYY-MM-DD-short-title.md`) with a running
   timeline.
3. **Mitigate first, diagnose properly second** — the immediate goal is
   restoring service (rollback per `docs/environments-and-promotion.md`
   section 3, fail over to a documented degraded mode via a circuit breaker's
   fallback per CLAUDE.md 2.6, or scale up), not finding root cause under
   pressure.
4. **Communicate** — for SEV-1/SEV-2, a status note (even a personal one, if
   solo-maintained) at the start and resolution of the incident.
5. **Verify recovery** — confirm SLIs are back within SLO before declaring
   resolved, not just "it looks fine."
6. **Postmortem** (SEV-1 and SEV-2 always; SEV-3 optional) — blameless,
   written within 48 hours, following the template in section 4.

## 3. Escalation & Guardrail Interaction

Some mitigations (destructive migration rollback, force-pushing a hotfix,
`terraform apply` to scale emergency capacity) intersect with the
human-in-the-loop guardrails in CLAUDE.md section 7 and
`.claude/hooks/pre-bash-guard.sh`. **Those guardrails are not suspended during
an incident.** An agent proposing a mitigation that would normally require
human confirmation still requires it during an incident — the human is
expected to be the one actively responding, so the confirmation step is not
the bottleneck it would be in a large organization, and skipping it during
exactly the highest-risk moments defeats its purpose.

## 4. Postmortem Template

```markdown
# Postmortem: <title>

## Summary
One paragraph: what happened, user impact, duration.

## Timeline
(UTC timestamps) Detection -> mitigation actions -> resolution.

## Root Cause
What actually caused it (not just the trigger — the underlying gap).

## What Went Well
## What Went Poorly
## Action Items
- [ ] Concrete, owned, dated follow-up (a monitoring gap, a missing test, a
      missing runbook step).

## Blameless Note
This postmortem evaluates the system and process, not individual performance
(including the AI agents involved) — the goal is a system that fails safer
next time.
```

## 5. Common Scenarios & First Response

| Scenario                                    | First response                                                        |
|------------------------------------------------|----------------------------------------------------------------------------|
| Event store unreachable                          | Check RDS health; if a failover is needed, promote the Multi-AZ standby (prod); verify outbox backlog once restored |
| External vision/LLM API down                       | Circuit breaker should already be open (CLAUDE.md 2.6) — verify fallback behavior is serving degraded responses, not erroring |
| RabbitMQ unavailable                                  | Outbox pattern means no event is lost; producers queue in the outbox table; verify the relay resumes once the broker recovers |
| Read model looks wrong/stale                             | Check consumer lag first (`docs/observability-slo.md`); if the event stream is intact, rebuild the projection rather than investigating the projector code under pressure |
| Suspected secret leak                                       | Rotate immediately per `docs/secrets-management.md` section 6, then investigate scope — rotation is not blocked on root-causing the leak |
