---
description: Implementation conventions for structured logging, tracing, metrics, and audit trail recording in NutriApp. Use whenever adding a new endpoint, event handler, or any action listed as auditable in CLAUDE.md.
---

# Observability & Audit — Implementation Conventions

Full rationale in `docs/observability-and-audit.md`.

## Structured Logging
```python
import structlog

logger = structlog.get_logger()

logger.info(
    "food_entry_logged",
    correlation_id=correlation_id,
    user_id=user_id,
    food_id=food_id,
)
```
- Always pass `correlation_id` explicitly (propagated from the inbound
  request/message, never regenerated mid-flow).
- Never log: passwords, raw tokens, full request bodies containing personal
  data. Use a redaction helper for known sensitive field names.

## Tracing
- Instrument with OpenTelemetry auto-instrumentation for FastAPI, the DB
  driver, and the message broker client where available; add manual spans
  around any custom logic worth isolating in a trace (e.g. the RAG retrieval
  step in `nutrition-assistant-service`).

## Metrics
Every service exposes `/metrics` (Prometheus format) with, at minimum:
- `http_requests_total{service, endpoint, status}`
- `http_request_duration_seconds{service, endpoint}`
- `circuit_breaker_state{service, dependency}`
- `message_consumer_lag{service, queue}` (where applicable)

## Audit Trail — When to Record One
Record an audit entry (not just a log line) for:
- Authentication events (login success/failure, logout, password change,
  lockout) — `identity-service`.
- Data export requests — `analytics-service`.
- Account/data deletion requests and their completion — across every service
  that holds a copy or projection of the affected data, `profile-service`
  and `diary-service` in particular given the special-category data they hold.
- Subscription/payment events (start, cancel, payment failure) —
  `billing-service`, per its no-raw-card-data rule.
- Any administrative action on another user's data.
- Any human-approved destructive operation (per CLAUDE.md section 7),
  including who approved it and when.

## Audit Record Implementation
```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class AuditRecord:
    audit_id: str
    occurred_at: datetime
    actor_id: str
    action: str
    target_type: str
    target_id: str
    outcome: str  # "success" | "failure"
    metadata: dict
    correlation_id: str
```
- Persisted to an append-only table/schema, with the application's DB role
  granted `INSERT` only (no `UPDATE`/`DELETE`) on that table.
- Audit records are exempt from normal data-retention deletion — they follow a
  separate, explicitly-approved compliance policy.

## Testing Requirements
- Every action listed above must have a test asserting an audit record is
  created with the correct `action`, `target_type`, and `outcome` on both the
  success and failure path.
- Log redaction of sensitive fields must have an explicit test (assert a
  password/token never appears in the emitted log line).
