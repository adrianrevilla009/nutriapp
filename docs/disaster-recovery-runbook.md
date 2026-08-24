# Disaster Recovery Runbook

`docs/backup-and-disaster-recovery.md` defines **what** is backed up and
the RPO/RTO targets. This document is the **how** — the actual sequence
of actions a human (or a human directing agents) executes during a real
disaster, and the periodic drill that verifies the sequence still works.
`docs/incident-response.md` covers day-to-day incidents (a service down,
elevated errors); this document is specifically for scenarios where
`docs/backup-and-disaster-recovery.md`'s backups must actually be
restored — a materially rarer and more severe class of event.

## 1. Disaster Scenarios Covered

Define which scenarios this runbook addresses — not every incident is a
disaster-recovery event. Typical scope:
- Full region outage (AWS region unavailable).
- Data corruption discovered in a write-model database, requiring
  point-in-time restore.
- Accidental/malicious destructive action bypassing guardrails (CLAUDE.md
  section 7) — e.g. a compromised credential ran a `DROP TABLE` despite
  every safeguard.
- Ransomware/security incident requiring restore from an isolated backup
  copy, per `docs/backup-and-disaster-recovery.md`'s cross-account backup
  copy.

## 2. Roles During a DR Event

NutriApp currently has a solo maintainer: all three roles below are held
by the same person simultaneously. This is written down explicitly so the
checklist doesn't silently assume a team that doesn't exist yet — if a
second maintainer joins, split these roles and update this table then.

| Role | Responsibility | Who |
|---|---|---|
| Incident Commander | Declares the DR event, makes the restore-vs-wait call, owns the timeline | Solo maintainer |
| Executor | Runs the actual restore commands | Solo maintainer |
| Communicator | Updates the status page (`docs/sla-and-contracts.md` section 5) and any affected customers | Solo maintainer |

## 3. Restore Procedure (per data store — reference `docs/backup-and-disaster-recovery.md`'s inventory)

For each data store in that document's backup inventory, define the
actual restore steps here, e.g.:

```
### RDS PostgreSQL (per-service databases)
1. Identify the target restore point (latest automated snapshot, or a
   specific point-in-time within the retention window).
2. Confirm with Incident Commander: restoring loses any writes after the
   restore point — is that acceptable, or is a different recovery path
   needed (e.g. replaying the event store from the outbox/broker if the
   write-model database is event-sourced per ADR-0002, which may recover
   more recent state than the last snapshot)?
3. Restore to a NEW instance (never overwrite the existing one in place)
   so the damaged instance remains available for forensic review if the
   cause of the incident is still unknown.
4. Re-point the service's connection configuration to the restored
   instance via the standard deployment pipeline (docs/ci-cd-strategy.md)
   — never a manual, undocumented config change, even during an
   incident (CLAUDE.md section 7 guardrails remain active during
   incidents per docs/incident-response.md).
5. Verify data integrity against a known-good checkpoint before declaring
   the restore complete.
```

Repeat this structure for the event store, Qdrant vector store, and
object storage entries in `docs/backup-and-disaster-recovery.md`'s
inventory.

## 4. Full Region Failover (only if `docs/multi-region-strategy.md` has an active secondary region)

If no secondary region is active, state that explicitly here: "no region
failover capability — a full region outage is a backup-restore event
into a new region, RTO per `docs/backup-and-disaster-recovery.md`, not an
instant failover." Do not leave this section silent, since silence reads
as "failover exists" by omission.

## 5. Post-Restore Validation Checklist

- All services report healthy (`docs/observability-slo.md` health
  checks).
- Data integrity spot-checks pass (a sample of records match expected
  state as of the restore point).
- Audit trail records the DR event itself: what happened, what was
  restored, to what point in time, and any data loss window
  (`docs/observability-and-audit.md`).
- Affected users/customers notified per `docs/sla-and-contracts.md`
  section 3 if any SLA is impacted.

## 6. Game Days (Drills)

- A full restore drill (not just a chaos-engineering resilience test per
  `docs/chaos-engineering.md`, which verifies application-level failure
  handling, not actual backup restoration) runs **quarterly**, restoring
  a real backup into an isolated environment and verifying the RTO/RPO
  targets in `docs/backup-and-disaster-recovery.md` are actually met, not
  just assumed.
- Every drill's actual measured RTO/RPO is recorded and compared against
  the target — a target that is never actually tested is not a reliable
  commitment.
- Findings from a drill (a step that took longer than expected, a
  missing credential, an out-of-date runbook step) update this document
  in the same cycle, not as a backlog item that lingers.

## 7. Ownership

`infra-agent` keeps the restore procedures in section 3 current as
infrastructure changes. The human maintainer (or Incident Commander role
above) owns actually declaring and running a DR event — this is
explicitly not something an agent initiates autonomously, consistent
with CLAUDE.md section 7's guardrails on destructive/high-risk actions.
