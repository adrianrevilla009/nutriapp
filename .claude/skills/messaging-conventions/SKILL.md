---
description: RabbitMQ naming, idempotency, and outbox pattern conventions for NutriApp. Use whenever publishing or consuming a domain event, or adding a new queue/exchange.
---

# Messaging Conventions — NutriApp

Full rationale in `docs/adr/0004-messaging-backbone.md` and CLAUDE.md
section 2.4.

## Naming Convention
`{producing_service}.{aggregate}.{event_type_snake_case}`, where
`{producing_service}` is unambiguously the **short** service name --
always drop a `-service`/`-svc` suffix (`identity`, not `identity-service`;
`profile`, not `profile-service`; `nutrition-calculation`, not
`nutrition-calculation-service`). e.g.:
- `diary.food_entry.logged`
- `catalog.product.updated`
- `identity.user.registered`
- `profile.profile.weight_recorded`
- `nutrition-calculation.target.updated`

Exchanges are topic exchanges per producing service, named
`{producing_service}.events` with the same short-name rule (`identity.events`,
`profile.events`, ...); queues are bound per consumer with a routing key
matching the events that consumer cares about.

## Library
`faststream` for new consumers/producers (async, type-safe, testable similarly
to FastAPI route handlers). `aio-pika` directly only when lower-level control
is genuinely needed.

## Outbox Pattern (mandatory when publishing alongside a DB write)
```python
async with db_session.begin():
    await event_store.append(event)          # source of truth
    await outbox_repository.enqueue(event)    # same transaction

# Separate relay worker/process:
async def relay_outbox():
    pending = await outbox_repository.fetch_unpublished()
    for event in pending:
        await publisher.publish(event)
        await outbox_repository.mark_published(event.event_id)
```

## Idempotent Consumption (mandatory)
```python
async def handle_entity_action(event: EntityActionEvent):
    if await processed_events_repository.already_processed(event.event_id):
        return  # duplicate delivery, no-op
    # ... apply effect ...
    await processed_events_repository.mark_processed(event.event_id)
```
Store processed event IDs with a reasonable TTL (long enough to cover
realistic redelivery windows, not indefinite).

## Consumer Error Handling
- A consumer that fails to process a message should nack/requeue with a
  limited retry count, then route to a dead-letter queue for manual
  inspection — never drop a failed message silently, never retry forever in a
  tight loop.
- Dead-lettered messages must be visible (logged, and ideally surfaced in
  metrics as `message_consumer_lag` or a dedicated dead-letter counter).

## Testing Requirements
- Contract test per event: payload matches the schema in
  `docs/events-catalog.md`.
- Idempotency test per consumer: processing the same event twice produces the
  same end state as processing it once.
- Outbox test: appending an event and the outbox row happens atomically (a
  simulated failure after the DB write but before the publish must not lose
  the event — it must still be relayed on retry).
