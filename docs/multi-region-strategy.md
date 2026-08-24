# Multi-Region Strategy

## 1. Current Status

**Not implemented. Single-region deployment** (per environment, per
`docs/terraform-and-infrastructure.md`), Multi-AZ within that region for
`prod`. This is a deliberate v1 scope decision, not an oversight — stated
explicitly here so it is a known, documented gap rather than a silent
assumption, per ADR-0021's discipline of writing down what is and isn't
being built for.

## 2. Why Not Multi-Region Now

Multi-region active-active (or even active-passive with fast failover)
multiplies operational complexity substantially: data replication lag
and conflict resolution for any service still using a single
write-master database, cross-region network cost, and doubling most of
`docs/terraform-and-infrastructure.md`'s resource inventory. None of
this is justified before a concrete trigger exists — consistent with the
measured-need discipline applied throughout this repo (ADR-0012,
ADR-0017, ADR-0021).

## 3. Activation Triggers (see also ADR-0021)

Revisit this document (and open a new ADR) when *any* of:
- A significant portion of the user base experiences latency
  meaningfully worse than the SLOs in `docs/observability-slo.md` due to
  distance from the single deployed region.
- A specific customer contract or regulation requires data residency in
  a specific geography this deployment doesn't cover (cross-reference
  `docs/sla-and-contracts.md` section 4 and
  `docs/compliance-mapping.md`).
- The single-region RTO in `docs/backup-and-disaster-recovery.md` is
  judged insufficient for the business (i.e. "restore from backup in
  region B" is too slow, and "already running in region B" is required
  instead).

## 4. What Changes When Activated (sketch — flesh out when the trigger fires)

- **Data layer**: any event-sourced service (ADR-0002) has a natural
  path to multi-region read replicas (the event stream can be shipped
  to a secondary region's read models), but the write side needs an
  explicit decision — active-passive (single write region, promoted on
  failover) is far simpler than active-active (conflict resolution
  required) and should be the default unless a specific requirement
  needs true active-active writes.
- **Messaging**: RabbitMQ (ADR-0004) does not natively support
  multi-region clustering as cleanly as Kafka does — this is one of the
  concrete factors that could tip ADR-0004's Kafka-fallback trigger,
  cross-reference it explicitly if this document's trigger fires first.
- **Edge**: CloudFront (ADR-0010) already routes globally by design —
  this layer needs no change; only the origin (API/backend) topology
  does.
- **Tenancy**: if ADR-0018 selected Option C (database-per-tenant),
  region assignment can be **per-tenant** (a specific customer's data
  lives in a specific region for residency reasons) rather than a
  wholesale platform migration — cross-reference `docs/multi-tenancy.md`
  section 3.

## 5. Ownership

`infra-agent` and `architecture-agent` jointly own evaluating whether a
trigger in section 3 has fired, as part of the same quarterly review
cadence as `docs/observability-slo.md` section 6 and ADR-0021. Actually
committing to a multi-region build is a significant cost decision
requiring explicit human approval, not something proposed and executed
by an agent alone.
