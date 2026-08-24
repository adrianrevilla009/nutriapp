# NutriApp — Architecture

High-level diagrams. See `CLAUDE.md` for the full rationale and rules behind
each decision, and `docs/adr/` for the formal Architecture Decision Records.

These diagrams show NutriApp's Phase 1 (MVP) services in the main flow;
`profile-service`, `activity-service`, `recipe-service`, `social-service`,
and `billing-service` (Phase 2) are omitted from the diagrams below for
readability but follow the same patterns — see `docs/product-requirements.md`
for the full service list and phasing.

## 1. Service Map

```
                              +-------------------+
                              |   Frontend (Web)   |
                              |  React + Next.js   |
                              +---------+-----------+
                                        |
                                        v
                              +-------------------+
                              |   Kong (API Gateway) |
                              | TLS, JWT, rate limit,|
                              |   CORS — no logic     |
                              +---------+-------------+
                                        |
                                        v
                              +-------------------+
                              |    bff-service       |
                              | (screen aggregation, |
                              |  no business logic)   |
                              +----+----+----+----+---+
                                   |    |    |    |
             +---------------------+    |    |    +---------------------+
             |                          |    |                          |
             v                          v    v                          v
   +-------------------+   +-------------------+   +-------------------+   +-------------------+
   | identity-service    |   | catalog-service     |   | diary-service    |   | food-recognition-service   |
   | (auth, sessions)    |   | (reference data,     |   | (CQRS + Event       |   | (optional: photo/    |
   |                     |   |  optional)           |   |  Sourcing)           |   |  media recognition)  |
   +---------+-----------+   +---------+-----------+   +---------+-----------+   +---------+-----------+
             |                         |                         |                         |
             +-------------------------+------------+------------+-------------------------+
                                                     |
                                          +----------v-----------+
                                          |     Message Broker     |
                                          |       (RabbitMQ)        |
                                          +----------+-----------+
                                                     |
                    +--------------------------------+--------------------------------+
                    |                                                                  |
                    v                                                                  v
        +-------------------+                                              +-------------------+
        | nutrition-           |                                              | analytics-service    |
        |  calculation-service   |                                              | (read models,          |
        | (CQRS + Event          |                                              |  trends, thresholds)   |
        |  Sourcing)                |                                              +---------+-----------+
        +---------+-----------+                                                          |
                  |                                                                    |
                  +----------------------------+---------------------------------------+
                                               |
                          +--------------------+--------------------+
                          v                                         v
               +-------------------+                     +-------------------------+
               |   nutrition-          |                     |  notification-service     |
               |    assistant-service    |                     |  (transactional email,     |
               |  (RAG over user data)   |                     |   push — see ADR-0011)      |
               +-------------------+                     +-------------------------+
```

`notification-service` is a pure event consumer (no service calls it
synchronously) — it subscribes to events from other services and turns
them into email/push per `docs/notifications.md`.

See ADR-0008 for why Kong (edge concerns) and `bff-service` (aggregation) are
kept as two separate things rather than one hand-rolled gateway.

## 2. Data Flow — Core Write Path (Event Sourcing)

```
User logs a food entry (from catalog search, a photo, or a barcode scan)
      |
      v
diary-service (application layer)
      |
      | 1. LogFoodEntryCommand -> domain validates -> FoodEntryLogged event
      v
Event Store (Postgres, append-only)
      |
      | 2. event persisted (source of truth)
      v
Outbox table (same transaction) --3--> RabbitMQ (diary.food_entry.logged)
      |
      +----------------------------+----------------------------+
      |                            |                             |
      v                            v                             v
Read-model projector      nutrition-calculation-service consumer  analytics-service consumer
(summary_view)             (recompute derived state)         (trend/anomaly ingestion)
      |
      v
Redis cache (hot aggregate, low-latency read)
```

## 3. Hexagonal Layout — Single Service Example (`diary-service`)

```
diary-service/
  domain/
    entities/<aggregate>.py           # Aggregate root, event-sourced
    value_objects/<value_object>.py
    events/<event_name>.py
    ports/<aggregate>_repository.py   # Protocol, implemented in infrastructure
    ports/event_publisher.py
  application/
    commands/<verb>_<aggregate>.py
    handlers/<verb>_<aggregate>_handler.py
    queries/get_<summary>.py
  infrastructure/
    http/router.py                   # FastAPI routes, thin controllers
    persistence/postgres_event_store.py
    persistence/read_model_projector.py
    messaging/rabbitmq_publisher.py
    messaging/outbox_relay.py
  tests/
    unit/domain/test_<aggregate>.py
    integration/test_postgres_event_store.py
    contract/test_<event_name>_schema.py
    e2e/test_<core_flow>.py
```

## 4. Human-in-the-Loop Pipeline (see CLAUDE.md section 6 for full detail)

```
Spec -> /implementation-plan -> [human approval] -> /test-plan ->
[human approval] -> /implementation-execution -> /test-execution ->
/implementation-review -> /test-review -> [human final approval] ->
/create-commit -> /create-pr -> [human merge approval]
```

## 5. Deployment Topology (AWS, per environment — see `docs/terraform-and-infrastructure.md`)

```
                         Route53 + ACM (TLS)
                                |
                                v
                  +---------------------------+
                  | CloudFront (CDN) + AWS WAF   |
                  | static assets, edge rate-limit,|
                  | managed rule groups (OWASP)      |
                  +--------------+---------------+
                                 |
                                 v
                     +----------------------+
                     |   ALB (Ingress)         |
                     +----------+-----------+
                                |
                                v
                +--------------------------------+
                |        EKS Cluster (VPC)          |
                |  +---------------------------+     |
                |  |   Kong (DB-less gateway)    |     |
                |  +--------------+--------------+     |
                |                 v                    |
                |   +-------------------------+         |
                |   |  bff-service + N domain    |         |
                |   |  services (Helm, on-demand  |         |
                |   |  + spot node groups)          |         |
                |   +-------------------------+         |
                |            |         |                |
                |            v         v                |
                |  +---------------+ +----------------+ |
                |  | RabbitMQ (Helm) | | Qdrant (Helm,   | |
                |  |                 | |  if AI assistant)| |
                |  +---------------+ +----------------+ |
                +--------------------------------+
                                |
              +-----------------+------------------+
              v                                     v
   +---------------------+                +----------------------+
   | RDS PostgreSQL          |                | ElastiCache (Redis)     |
   | (per-service databases,  |                | (shared cache layer)      |
   |  Multi-AZ in prod)         |                +----------------------+
   +---------------------+
              |
              v
   Automated snapshots + cross-account backup copy
   (docs/backup-and-disaster-recovery.md)
```

Secrets flow: AWS Secrets Manager -> External Secrets Operator -> Kubernetes
`Secret` -> pod env vars, scoped per service via IRSA (ADR-0007,
`docs/secrets-management.md`). Every AWS resource above is provisioned by
Terraform (ADR-0006, `infra/terraform/`), never created by hand.

CloudFront + WAF is the one edge layer Terraform-provisioned ahead of the
ALB — see ADR-0010 and `docs/edge-and-cdn.md` for what it fronts (static
frontend assets and any per-user media, e.g. uploaded photos, as short-TTL
signed URLs) versus what it passes through unmodified (API traffic, which
Kong still rate-limits and validates per ADR-0008).
