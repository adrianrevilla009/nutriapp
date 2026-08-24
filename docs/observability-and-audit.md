# Observability and Audit

## 1. Structured Logging

- All services log in structured JSON via `structlog`.
- Every log line includes: `timestamp`, `level`, `service_name`, `correlation_id`,
  `event` (short machine-readable name), and a human-readable `message`.
- `correlation_id` is generated at the API Gateway for every inbound request and
  propagated:
  - Across HTTP calls via the `X-Correlation-Id` header.
  - Across messages via the `correlation_id` field in event metadata.
- Never log secrets, passwords, tokens, or full request/response bodies that may
  contain personal data. Redact known sensitive fields at the logging middleware
  level.

## 2. Distributed Tracing

- OpenTelemetry SDK instruments every service (HTTP server, HTTP client, DB
  driver, message broker client).
- Local development exports traces to a Jaeger container (`docker-compose.yml`).
- Every trace span includes the `correlation_id` as an attribute for cross-
  referencing with logs.

## 3. Metrics

- Every service exposes a Prometheus-compatible `/metrics` endpoint
  (`prometheus-client`).
- Minimum metrics per service: request count and latency histogram per endpoint,
  error rate per endpoint, circuit breaker state per external dependency,
  message consumer lag (where applicable).

## 4. Audit Trail

Audit records are distinct from operational logs: they are business-meaningful,
immutable, append-only, and retained under a separate retention policy (never
deleted by normal data lifecycle rules).

### 4.1 What must be audited
- Authentication events: login success/failure, logout, password change,
  account lockout.
- Data export requests (a user exporting their own history/report).
- Account deletion requests and their completion, including the
  crypto-shredding step described in `docs/data-protection-and-privacy.md`
  section 4.
- Consent grants/withdrawals (`docs/data-protection-and-privacy.md` section 1).
- Any administrative action performed on another user's data.
- Destructive operations approved via the human-in-the-loop guardrails
  (CLAUDE.md section 7), including who approved them and when — this now
  also covers `terraform apply`/`destroy` and `kubectl delete`/`helm
  uninstall` approvals, not just database/git operations.

### 4.2 Audit record schema
Each audit record includes: `audit_id`, `occurred_at`, `actor_id` (who performed
the action — a user, an admin, or an agent acting on behalf of a human-approved
action), `action`, `target_type`, `target_id`, `outcome` (success/failure),
`metadata` (free-form JSON for action-specific context), `correlation_id`.

### 4.3 Storage
- Audit records are stored in an append-only table, in a separate schema from
  operational data, with `INSERT`-only permissions granted to the application
  role (`UPDATE`/`DELETE` are not granted at the database level).
- Audit records are never truncated by the destructive-migration guardrail
  without an explicit, separately-approved compliance decision.

## 5. Alerting & SLOs

Superseded by `docs/observability-slo.md`, which defines concrete SLIs/SLOs,
error budgets, and burn-rate alerting per service — this is no longer future
work. See `docs/incident-response.md` for what happens when an alert fires.
