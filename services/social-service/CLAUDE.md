# social-service -- agent-scoped notes

This file is scoped guidance for any agent working inside
`services/social-service/`. It does not replace the root `/CLAUDE.md`
(architecture, workflow, guardrails) or `.claude/agents/social-agent.md`
(bounded context, domain responsibilities, rules) -- read both first,
plus `.claude/skills/saga-conventions/SKILL.md` and
`.claude/skills/resilience-patterns/SKILL.md` before touching
`application/entitlement_check.py` or
`infrastructure/messaging/billing_events_consumer.py` -- mandatory,
non-negotiable reading.

## Quick orientation

- Hexagonal layout: `domain/` -> `application/` -> `infrastructure/`,
  dependencies point inward only (ADR-0001). The domain layer never
  imports FastAPI, SQLAlchemy, httpx, aio_pika, or pydantic.
- Event-driven CRUD (ADR-0002), not event-sourced -- `Follow` is a
  conventional row per follower/followee pair.
- Self-follow is rejected STRUCTURALLY in `domain/entities/follow.py`'s
  `__post_init__` -- not just an application-layer check.
- Unfollow is a genuine HARD delete -- `FollowRepositoryPort.delete()` is
  a real delete method, unlike `recipe-service`'s repository (no delete
  method at all, soft-unpublish only). A confirmed, deliberate deviation
  from `recipe-service`'s convention (see README.md).
- Feed composition is fan-out-on-read: `feed_entries` is populated ONLY
  by consuming `recipe-service`'s `RecipePublished`/`RecipeUnpublished`.
  There is no HTTP route or application command to create a `FeedEntry`
  directly.

## Never do this

- Never write a fallback `EntitlementCheckPort` result back into
  `entitlement_cache` -- `application/entitlement_check.py`'s
  `is_user_entitled` has no reference to the cache repository's write
  method at all; keep it that way.
- Never add a `FollowRepositoryPort` parameter to
  `HandleEntitlementRevokedHandler`'s constructor -- revocation is
  non-destructive by construction (structurally guarded, tested by
  `tests/unit/application/test_handle_entitlement_revoked.py::test_handler_never_references_follow_repository_port`).
- Never add an entitlement-port parameter to `ListFollowingHandler`/
  `ListFollowersHandler` -- these two queries are NOT Pro-gated
  (structurally guarded the same way).
- Never make a live call to a real `billing-service` or `recipe-service`
  instance in this service's own test suite -- `httpx.MockTransport`
  fixtures (`tests/fixtures/billing_responses/`) and fixture RabbitMQ
  events (`tests/fixtures/recipe_events/`, inlined in the consumer
  integration tests) only.
- Never share circuit-breaker state with any other integration -- there is
  only one breaker (`billing_entitlement_check`); if a second synchronous
  external call is ever added, give it its own independently-named
  breaker and its own `httpx.AsyncClient`.
- Never add a synchronous call to `recipe-service` -- feed composition is
  entirely async via consumed events (implementation plan section 1.8).

## Where things live

- Ports: `domain/ports/*.py` (Python `Protocol`s): `FollowRepositoryPort`,
  `FeedRepositoryPort`, `EntitlementCacheRepositoryPort`,
  `ProcessedEntitlementEventsRepositoryPort`,
  `ProcessedRecipeEventsRepositoryPort`, `EntitlementCheckPort`,
  `OutboxRepositoryPort`, `EventPublisherPort`.
- Adapters: `infrastructure/external/billing_entitlement_client.py`,
  `infrastructure/persistence/` (six Postgres repositories),
  `infrastructure/messaging/` (`BillingEventsConsumer`,
  `RecipeEventsConsumer`, `RabbitMqEventPublisher`, `OutboxRelayWorker`).
- Composition root: `infrastructure/composition_root.py` -- the only
  place concrete adapters are wired to ports.
- Shared cross-handler helper (not a port, not a command):
  `application/entitlement_check.py` (used by follow/unfollow/feed).
- Tests mirror `testing-strategy` SKILL.md's layout under `tests/`. Fake
  ports for unit tests live in `tests/fixtures/factories.py`.

## Coverage floors

Domain >= 90%, application >= 85%, infrastructure >= 70% (CLAUDE.md
section 3).
