# ADR-0004: Messaging Backbone — RabbitMQ with Kafka as Documented Fallback

## Status
Accepted

## Date
2026-08-23

## Context
Services need to communicate domain events asynchronously (e.g. `catalog-service`
publishes `ProductUpdated`, `analytics-service` consumes it to refresh trend
projections). The choice of broker affects operational complexity, local
development ergonomics, and how event replay/stream processing is done later.

## Decision
Use **RabbitMQ** as the default message broker for all inter-service
communication in NutriApp. Use `faststream` (or `aio-pika` for lower-level
control) as the Python client library.

Kafka is documented here as the fallback option if/when any of the following
become real requirements:
- Need to replay the full event history of a topic for a new consumer
  (RabbitMQ is not designed as a long-term event log).
- Need high-throughput stream processing (e.g. real-time trend computation
  across all users at scale).
- Need strict ordering guarantees per partition key at high volume.

If any of the above becomes true, propose a new ADR superseding this one before
migrating; do not silently introduce Kafka alongside RabbitMQ.

## Considered Alternatives
- **Kafka from day one** — better fit for event sourcing at scale and long-term
  event replay, but meaningfully higher operational complexity (ZooKeeper/KRaft,
  partition management, more resource-hungry) for a project at this stage.
- **Redis Streams** — lighter than both, but weaker delivery guarantees and
  ecosystem tooling (schema registry, contract testing) compared to RabbitMQ.
- **Direct HTTP calls only (no broker)** — rejected outright; it would force
  synchronous coupling and remove the resilience benefits described in
  CLAUDE.md section 2.6.

## Consequences
### Positive
- Lower operational footprint for local development (single container in
  `docker-compose.yml`) and for a solo/small-team deployment.
- `faststream` gives type-safe, testable message handlers similar in ergonomics
  to FastAPI route handlers.

### Negative / Trade-offs
- RabbitMQ is not an event log; `diary-service` and `nutrition-calculation-service` still
  need their own durable Event Store (Postgres table) as the source of truth
  for event sourcing — RabbitMQ is only the transport for notifying other
  services, not the system of record for events.
- Migrating to Kafka later, if needed, requires re-implementing consumers/
  producers against a different client library.

### Follow-up actions
- Document exchange/queue naming convention in
  `.claude/skills/messaging-conventions/SKILL.md`.
- `devops-agent` provisions RabbitMQ in `docker-compose.yml` with management
  UI enabled for local debugging.

## References
- CLAUDE.md, section 2.4
- ADR-0002 (event sourcing — clarifies RabbitMQ is transport, not the event store)
