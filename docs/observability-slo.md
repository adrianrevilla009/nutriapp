# Observability, SLOs & Alerting

Expands `docs/observability-and-audit.md` (which covers logging/tracing/audit
mechanics) with the *targets and response process* — what "healthy" means
numerically, and what happens when it isn't.

## 1. Service Level Indicators (SLIs) Tracked per Service

- Request latency (p50/p95/p99), by endpoint.
- Error rate (5xx / total requests), by endpoint.
- Availability (successful health-check ratio over a rolling window).
- For async consumers: event processing lag (time between publish and
  successful consume) and dead-letter queue depth.
- For external-dependency-heavy services (`food-recognition-service`, `nutrition-assistant-service`):
  circuit breaker state (open/closed/half-open) and external call error rate,
  tracked separately from the service's own error rate.

## 2. Service Level Objectives (SLOs)

| Service              | Availability SLO | Latency SLO (p95)         | Error budget window |
|------------------------|---------------------|---------------------------------|--------------------------|
| `identity-service`        | 99.9%                  | 300ms (login), 100ms (token verify) | 30 days                    |
| `diary-service`           | 99.9%                  | 250ms (write), 150ms (read via cache)  | 30 days                    |
| `nutrition-calculation-service`           | 99.9%                  | 150ms (read model)                       | 30 days                    |
| `catalog-service`                | 99.5%                  | 500ms (search)                              | 30 days                    |
| `food-recognition-service`                   | 99.0% (bounded by external provider's own SLA) | 3s                                              | 30 days                    |
| `nutrition-assistant-service`                     | 99.0% (bounded by external LLM API's own SLA)      | 5s (TTFB < 1s)                                     | 30 days                    |
| `analytics-service`                     | 99.5%                  | 1s (trend queries, can be heavier)                     | 30 days                    |
| Kong gateway / BFF                        | 99.95%                 | +20ms overhead max vs. direct service call               | 30 days                    |

SLOs are deliberately looser for `food-recognition-service` and `nutrition-assistant-service`
because their ceiling is set by a third-party provider outside our control —
the internal error budget still counts *our* failures (timeouts we didn't
configure well, missing fallback), not the provider's own downtime, which is
tracked and reported on separately.

## 3. Error Budgets

- A 30-day rolling error budget per service, derived from its availability
  SLO (e.g. 99.9% availability = ~43 minutes of budget per 30 days).
- **Budget policy**: if a service has burned more than 50% of its error
  budget in the current window, new feature work for that service pauses in
  favor of reliability work, until the budget recovers — a real trade-off
  decision, not just a dashboard number. The human maintainer makes this call
  explicitly; agents flag budget burn in their implementation plans when
  relevant (`architecture-agent` or `devops-agent`).

## 4. Alerting

- **Prometheus Alertmanager** (via the managed Amazon Managed Prometheus
  stack, per `docs/terraform-and-infrastructure.md`), routing to a single
  notification channel appropriate for a solo maintainer (e.g. a dedicated
  Slack channel or PagerDuty free tier), not a full on-call rotation.
- Alert on **symptoms, not causes**: page on SLO burn-rate (multi-window,
  e.g. fast burn over 1h AND slow burn over 6h, standard Google SRE burn-rate
  alerting), not on every individual metric threshold crossing.
- Ticket-only (non-paging) alerts for: elevated but not SLO-threatening error
  rates, disk usage trending toward capacity, certificate expiry within 30
  days, dependency vulnerability scan findings.

## 5. Dashboards

- One Grafana dashboard per service (latency, error rate, saturation,
  traffic — the four golden signals), generated from a shared dashboard
  template to stay consistent.
- One system-wide dashboard: event processing lag across all consumers,
  circuit breaker states, external API cost-relevant call volume (vision/LLM
  calls per hour, since these are billed).

## 6. Review Cadence

SLOs and alert thresholds are reviewed whenever a new service ships, and
otherwise quarterly — an SLO set once at launch and never revisited tends to
become either meaninglessly loose or a constant false-alarm source as real
traffic patterns emerge.
