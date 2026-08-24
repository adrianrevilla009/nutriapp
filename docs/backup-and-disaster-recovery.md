# Backup & Disaster Recovery

## 1. What Must Survive a Disaster

Ranked by priority, since restoration order matters:

1. **Event stores** (`diary-service`, `nutrition-calculation-service`) — the source of
   truth per ADR-0002. Losing these loses the ability to rebuild any read
   model; this is the single highest-priority dataset in the system.
2. **Identity data** (`identity-service`'s user/credential store).
3. **Other services' write-model databases** (catalog, analytics raw data).
4. **Read models / projections** — technically disposable (rebuildable by
   replaying events per ADR-0002), but restoring from a snapshot is far
   faster than a full replay for services with a long event history, so they
   are still backed up as a performance optimization, not a correctness
   requirement.
5. **Qdrant vector store** (`nutrition-assistant-service`) — rebuildable from source data
   (user history) but re-embedding at scale costs time and, if using a
   paid embedding API, money.
6. **Object storage** (any retained uploaded media, per the opt-in retention
   policy in `docs/data-protection-and-privacy.md`).

## 2. Backup Mechanisms

| Store                    | Mechanism                                              | Frequency                | Retention          |
|-----------------------------|-----------------------------------------------------------|------------------------------|-----------------------|
| RDS (all services)              | Automated snapshots + point-in-time recovery (PITR)             | Continuous (PITR), daily snapshot | 35 days (PITR window), 1 year for monthly snapshots |
| Event store specifically         | Same as RDS, **plus** a logical export (event stream dump) to S3, append-only, cross-region | Daily logical export                | 3 years minimum (or your domain's regulatory retention requirement) |
| ElastiCache (Redis)                | No backup — treated as pure cache, rebuildable from source on cold start | N/A                                    | N/A                        |
| RabbitMQ                             | Not backed up directly — it is a transport, not a store; the outbox pattern (CLAUDE.md 2.4) guarantees no event is lost even if the broker is | N/A                                    | N/A                        |
| Qdrant                                 | Volume snapshots (EBS snapshot if self-hosted) | Daily                                | 30 days |
| Terraform state                          | S3 versioning (already durable) + cross-region replication for the state bucket | Continuous | Indefinite |
| Object storage (uploaded media, opt-in)        | S3 versioning + lifecycle policy to Glacier for older-than-90-days | Continuous | Per user retention preference |

## 3. Cross-Region / Cross-Account Protection

- Daily event-store logical exports and RDS snapshots are copied to a
  **separate AWS account** (or at minimum a separate region) than production,
  so a compromised or misconfigured production account cannot delete its own
  backups.
- Terraform state bucket has `MFADelete` enabled in `prod`.

## 4. Recovery Objectives

| Environment | RPO (max acceptable data loss) | RTO (max acceptable downtime) |
|--------------|-----------------------------------|-----------------------------------|
| `prod`         | 5 minutes (via PITR) for the event store; 24h for less-critical read-only projections | 1 hour for a single-service failure; 4 hours for a full-region failure |
| `staging`       | 24 hours                             | 4 hours (not business-critical) |
| `dev`             | None (ephemeral, rebuildable from scratch) | N/A |

## 5. Restore Runbook (must be tested, not just written)

1. Identify the failure scope (single table, single service DB, full
   region).
2. For a single-service RDS failure: restore from the latest automated
   snapshot or PITR to a new instance, repoint the service's connection
   secret (via the rotation flow in `docs/secrets-management.md`), verify
   health checks pass before routing traffic.
3. For event-store corruption specifically: restore from the daily logical
   export, then **replay** any events from RabbitMQ's dead-letter/retry queue
   or from the outbox table that postdate the export, before declaring the
   event store consistent again.
4. For read-model corruption only (event store intact): the fix is to
   **rebuild the projection from the event stream**, not restore from backup
   — this is the whole point of CQRS/ES (ADR-0002). Prefer this path whenever
   only the read side is affected.
5. Update the incident timeline in `docs/incident-response.md`'s log and run
   a blameless postmortem once service is restored.

## 6. Game Days

A **disaster recovery drill** (deliberately restoring `staging` from a backup
into a scratch environment) runs at minimum quarterly, and after any
significant change to the backup mechanism itself. An untested backup is not
a backup — this drill is not optional, even for a solo-maintained project.
