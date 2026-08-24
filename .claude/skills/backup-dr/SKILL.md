---
description: Backup and disaster recovery conventions for NutriApp. Use whenever touching backup configuration, writing a restore procedure, or assessing the blast radius of a data-affecting change.
---

# Backup & DR Conventions — NutriApp

Full policy: `docs/backup-and-disaster-recovery.md`.

## Rules
- The event store (`diary-service`, `nutrition-calculation-service`) is the
  highest-priority dataset in the system — any infra change affecting its
  backup mechanism requires explicit human review, not just standard PR
  approval.
- Read-model corruption is fixed by **rebuilding the projection from events**,
  never by restoring from backup, when the event store itself is intact
  (ADR-0002). Restoring from backup is for write-model/event-store loss only.
- Any change to backup frequency/retention updates the RPO/RTO table in
  `docs/backup-and-disaster-recovery.md` in the same PR.
- DR drills (quarterly minimum) are tracked; a drill that fails blocks
  closing the drill ticket until the gap is fixed and re-tested — an
  untested backup is not a backup.
