# Cost Management

Infrastructure choices throughout this project (EKS, RDS Multi-AZ, Secrets
Manager, self-hosted RabbitMQ/Qdrant) trade operational simplicity for real
AWS spend. This document tracks the levers used to keep that spend
proportionate to a solo/early-stage project, without undermining the
production-grade posture defined elsewhere.

## 1. Non-Prod Cost Controls

- **`dev` scales to zero outside working hours**: a scheduled Lambda (or
  `kube-downscaler`) scales all `dev` namespace deployments to 0 replicas and
  stops the `dev` RDS instance nightly/weekends, resuming automatically on a
  schedule or on-demand via a manual trigger.
- **Spot instances** for `dev` and `staging` node groups entirely (not just a
  portion) — interruption tolerance is acceptable in non-prod.
- **Single-AZ, smallest-viable-size RDS/ElastiCache** in `dev`; `staging`
  mirrors `prod` topology but at reduced instance sizes, not reduced
  architecture (so load tests remain representative).

## 2. Prod Cost Controls (without compromising the SLOs in `docs/observability-slo.md`)

- **Mixed on-demand + spot node groups**: baseline capacity on-demand,
  burst/interruption-tolerant workloads (async event projectors, background
  jobs) on spot.
- **Right-sized resource requests**, revisited quarterly against actual
  Prometheus usage data — not set once at launch and forgotten (over-
  provisioned requests are one of the most common silent cost leaks in
  Kubernetes).
- **RDS reserved instances or Savings Plans** once traffic patterns are
  predictable enough to commit (not before — committing early to guessed
  capacity is its own cost risk).

## 3. Metered External Dependencies

`food-recognition-service` (vision API) and `nutrition-assistant-service` (LLM provider) are
**usage-billed, not infrastructure-billed** — their cost scales with product
usage directly, which is a different risk profile than fixed infra spend:
- Circuit breakers (CLAUDE.md 2.6) double as cost protection: an open breaker
  stops calls to a failing *or accidentally-looping* external dependency.
- Per-user or per-day rate limits on AI-chat and vision-analysis requests,
  independent of the general API rate limiting in `docs/api-standards.md`,
  specifically to cap worst-case external spend from a single account (abuse
  or a client-side bug causing a retry storm).
- A budget alert (AWS Budgets + a cost-tracking Grafana panel wired to
  provider usage APIs where available) on both AWS spend and third-party AI
  API spend, reviewed at the same cadence as SLOs.

## 4. Tagging & Attribution

Every resource is tagged per `docs/terraform-and-infrastructure.md` section
5 (`Service`, `Environment`, `CostCenter`), enabling AWS Cost Explorer
breakdowns by service — necessary to know which service is actually driving
spend before optimizing the wrong thing.

## 5. Review Cadence

Cost is reviewed monthly against the previous month, and any month-over-month
increase greater than 20% without a corresponding, expected cause (a real
traffic increase, a deliberate new feature) is investigated before the next
billing cycle closes, not retroactively at quarter-end.
