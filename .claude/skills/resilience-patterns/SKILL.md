---
description: Circuit breaker, retry, timeout, and bulkhead conventions for NutriApp. Use whenever adding or modifying a synchronous inter-service call or an external API integration (scraping targets, vision API, LLM calls).
---

# Resilience Patterns — NutriApp Conventions

Full rationale in CLAUDE.md section 2.6. Mandatory for every synchronous
outbound call this system makes, internal or external.

## Circuit Breaker
- Library: `pybreaker` for sync code, `purgatory` for async.
- Every external dependency (an HTTP call to another service, a third-party
  source, the vision provider, an LLM call) gets its own named circuit breaker
  instance — never share one breaker across unrelated dependencies.
- Configuration (document the chosen values per integration in that service's
  `README.md`):
  - `fail_max`: number of consecutive failures before opening the circuit.
  - `reset_timeout`: how long the circuit stays open before allowing a trial
    request (half-open state).
- When a circuit is open, fail fast with an explicit, typed exception the
  application layer can catch and turn into a documented fallback behavior —
  never let callers block waiting on a call you already know is failing.

## Retry with Backoff
- Library: `tenacity`.
- Exponential backoff with jitter, a maximum number of attempts, and a maximum
  total wait time.
- **Never retry a non-idempotent operation** unless it carries a deduplication
  key the receiving side can use to ignore a duplicate (e.g. an `event_id` or
  an idempotency key header).
- Retries happen *inside* the circuit breaker's failure counting, not as a way
  to avoid tripping it — a call that needed 3 retries to succeed should still
  count toward the breaker's health signal if it ultimately failed.

## Timeout
- Every outbound call (HTTP client, DB driver, message broker client) has an
  explicit timeout configured — there is no such thing as an acceptable
  unbounded wait in this codebase.
- Timeouts are tuned per integration based on that dependency's expected
  latency profile, not copy-pasted defaults.

## Bulkhead
- Isolate connection/thread pools per external dependency so that one slow or
  failing dependency cannot exhaust resources needed by calls to a healthy
  one. In practice: a dedicated `httpx.AsyncClient` (with its own connection
  pool limits) per external integration, not one shared client for everything.

## Fallback Behavior
Every endpoint or use case that depends on an external call must have an
explicit, documented fallback for when that call fails or the circuit is open:
- Serve cached data (see `.claude/skills/caching-strategy/SKILL.md`) if
  slightly stale data is acceptable.
- Return a partial result with a clear indicator of what is missing.
- Fail the specific operation clearly rather than cascading the failure to
  unrelated functionality.

## Testing Requirements
- Unit/integration tests must cover: the circuit opening after the configured
  failure threshold, the fallback behavior firing correctly while open, and
  the circuit recovering (half-open -> closed) after `reset_timeout`.
- Simulate timeouts explicitly in tests (do not rely on a real slow dependency
  to exercise this path).
