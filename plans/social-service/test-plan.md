# Test Plan — `social-service` (+ `notification-service` PR A)

**Status:** Approved
**Date approved:** 2026-08-31
**Approved by:** human, delegated in-session — see implementation-plan.md's approval note.
**Stage:** 4 (Test Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Implements:** `/plans/social-service/implementation-plan.md`

No test code has been written yet — this defines cases only, per TDD.

## 1. Unit test cases — `social-service`

**Value objects:**
- `Follow(follower_id, followee_id)` — `follower_id == followee_id` raises (self-follow rejected at the domain level, not just the application layer — a structural guard).
- `FeedEntry(recipe_id, author_id, title, published_at)` — basic field validation.

**`FollowUserHandler`** (fake `FollowRepositoryPort`, fake `EntitlementCacheRepositoryPort`, fake `EntitlementCheckPort`, fake outbox):
- Entitled user (cache hit) following a not-yet-followed user → `Follow` persisted, `UserFollowed` published with the correct `follow_id`/`follower_id`/`followee_id` payload.
- Self-follow attempt (`follower_id == followee_id`) → rejected with a typed error before any repository write, no event published.
- Already-following the same user → idempotent 200-equivalent (existing row returned), no duplicate `Follow` row, no duplicate `UserFollowed` published (assert `outbox.enqueue_calls == 0` on the repeat call).
- Unentitled user (cache hit, `entitled=False`) → rejected with a typed "not entitled" error before any repository write is attempted (assert the fake `FollowRepositoryPort`'s write method is never called — cheapest check wins, mirrors `recipe-service`'s `PublishRecipeHandler` pattern).
- No cache entry yet for this user → falls back to `EntitlementCheckPort`; a `True` result proceeds, a `False` result rejects — either way, the fallback result is **not** written into `entitlement_cache` (assert the fake cache-repository's write method is never called in this path — the single most important structural invariant, per `recipe-service`'s precedent).

**`UnfollowUserHandler`:**
- Following user unfollows → `Follow` row removed (hard delete is acceptable here, unlike `recipe-service`'s soft-unpublish-only rule — a follow relationship has no "history" value once ended; confirm this against implementation-plan.md, which does not mandate soft-delete for `Follow`), `UserUnfollowed` published.
- Not currently following → idempotent no-op, no event published (assert `outbox.enqueue_calls == 0`).
- Unentitled user → rejected before any repository write (same cheapest-check-first pattern as follow — per the plan's §9.1 decision to gate unfollow too).

**`HandleEntitlementGrantedHandler`/`HandleEntitlementRevokedHandler`** (fake `ProcessedEntitlementEventsRepositoryPort`, fake `EntitlementCacheRepositoryPort`):
- Valid event → cache row upserted (`entitled=True`/`False`), event marked processed.
- Same `event_id` processed twice → second call is a no-op (assert the fake cache-repository's write method is called exactly once total across both invocations).
- `HandleEntitlementRevokedHandler` specifically → assert the fake `FollowRepositoryPort`'s delete/query methods are never called (revocation only flips the cache flag, never touches existing follows — implementation-plan.md §1.2's "non-destructive" rule, a structural guard).

**`HandleRecipePublishedHandler`/`HandleRecipeUnpublishedHandler`** (fake `ProcessedRecipeEventsRepositoryPort`, fake `FeedRepositoryPort`):
- `RecipePublished` → `feed_entries` row upserted with `recipe_id`/`author_id`/`title`/`published_at` from the event payload.
- `RecipeUnpublished` for a recipe with an existing `feed_entries` row → row removed.
- `RecipeUnpublished` for a recipe with no existing `feed_entries` row (never published in this consumer's lifetime, or already removed) → idempotent no-op, no error.
- Same `event_id` processed twice (either event type) → second call is a no-op (assert the fake feed-repository's write method is called exactly once total — independent idempotency ledger from the entitlement-events consumer, per implementation-plan.md §3's two-table design).

**`GetFeedHandler`** (fake `FeedRepositoryPort`, fake `FollowRepositoryPort`, fake entitlement ports):
- Entitled user with two followed authors, one with a published recipe in `feed_entries` and one with none → feed contains exactly the one entry, ordered correctly if a third entry from a different followed author with an earlier `published_at` is added.
- Unentitled user → rejected before any `FeedRepositoryPort`/`FollowRepositoryPort` query is attempted (assert both fakes' query methods are never called).
- A recipe present in `feed_entries` from an author the user does NOT follow → never appears in that user's feed (join correctness, not just "the row exists somewhere").

**`ListFollowingHandler`/`ListFollowersHandler`:**
- Not Pro-gated — an unentitled user's request succeeds (assert no entitlement-port call is made at all, structurally distinguishing these two read-only queries from every Pro-gated one above).

## 2. Integration test cases — `social-service`

- `BillingEntitlementClient` — against a fixture HTTP server: valid credential + entitled/unentitled user → correct boolean; simulated repeated failures trip the `billing_entitlement_check` circuit breaker (call-count assertions, recovery verified after `reset_timeout`, per `resilience-patterns/SKILL.md`).
- Postgres repositories (`follows`, `feed_entries`, `entitlement_cache`, `processed_entitlement_events`, `processed_recipe_events`, `outbox`) — round-trip persistence via testcontainers Postgres. Explicitly test the `follows` table's `(follower_id, followee_id)` unique constraint is enforced at the DB level (a second insert attempt for the same pair raises, defense-in-depth beneath the application-layer idempotency check).
- `billing_events_consumer` — against testcontainers RabbitMQ: publishing the same `EntitlementGranted`/`EntitlementRevoked` event twice results in exactly one cache upsert; a handler that raises is nacked/requeued up to the configured limit, then dead-lettered.
- `recipe_events_consumer` — same idempotency/DLQ shape as above, independently, against `RecipePublished`/`RecipeUnpublished` fixture events (not real calls to `recipe-service`).
- Outbox relay worker — appending an event and the outbox row happens atomically; a simulated failure after the DB write but before the publish must not lose the event.
- Alembic migration `0001` applies cleanly to an empty database.

## 3. Contract test cases — `social-service`

- `POST /api/v1/social/follows` — `201`/`200` (idempotent) for a valid follow; `422` for a self-follow attempt; `402`/`NOT_ENTITLED` for an unentitled user (reusing `recipe-service`'s exact convention, implementation-plan.md §3); `401` unauthenticated.
- `DELETE /api/v1/social/follows/{followee_id}` — `200`/`204` on success or idempotent no-op; `402`/`NOT_ENTITLED` for an unentitled user.
- `GET /api/v1/social/follows/following` / `.../followers` — `200` with the correct list; succeeds for an unentitled user (not gated).
- `GET /api/v1/social/feed` — `200` with matching feed entries for an entitled user, correctly ordered and correctly excluding non-followed authors' entries; `402`/`NOT_ENTITLED` for an unentitled user.
- `UserFollowed`/`UserUnfollowed` (v1) — each published payload matches `docs/events-catalog.md`'s documented schema (§1.5 of the implementation plan).

## 4. E2E test cases

Not built here, same reasoning as every prior service's plan (no cross-service E2E harness exists yet in this repo). Note (not previously true): CLAUDE.md §3's journey 3 ("Upgrade to Pro → publish a recipe → another user finds it in recipe search") does not depend on `social-service` at all — that journey is `recipe-service`'s alone. `social-service` doesn't complete a new named E2E journey from CLAUDE.md §3; it's additive Pro-gated functionality.

## 5. Event-sourcing-specific cases

**Not applicable.** `social-service` uses event-driven CRUD (implementation plan §2), not event sourcing.

## 6. Unit/integration/contract test cases — `notification-service` (PR A, §6 of the implementation plan)

- `NotificationCategory.push("new_follower")` — valid; confirm it's correctly excluded from `EMAIL_CATEGORIES` (a category name collision/reuse check, mirroring the existing channel-scoping tests for `fasting`/`meal`/`water`).
- `get_notification_preferences.py` — confirm `"new_follower"` appears in the default preference list returned for a user with no explicit override (proves the "no migration needed" design decision from implementation-plan.md §7 is correct in practice, not just in theory).
- `social_events_consumer.py` — against testcontainers RabbitMQ: a fixture `UserFollowed` event (not a real call to `social-service`) results in exactly one push-notification dispatch attempt; same `event_id` delivered twice → exactly one dispatch (idempotency, mirroring `diary_events_consumer.py`'s existing test shape); a user who has opted out of the `new_follower` push category → no dispatch attempted at all (suppressibility, `is_transactional=False` confirmed to actually suppress, not just be labeled correctly).
- `new_follower_v1.json.j2` template — contract test rendering a fixture payload, confirming required fields are present, mirroring `meal_reminder_v1.json.j2`'s existing contract test shape.

## 7. Coverage expectation

`social-service`: domain layer (`Follow`, `FeedEntry`) has enumerable edge cases — expect close to 100%, clearing the ≥90% floor. Application layer's ten handlers (six commands + four queries, counting `follow`/`unfollow`/two entitlement handlers/two recipe-event handlers/`list_following`/`list_followers`/`get_feed`) each have 2-5 cases above, deliberately covering entitlement-gating, idempotency, and the two independent event-consumer ledgers — clears ≥85%. Infrastructure layer's client (full circuit-breaker matrix), five repositories, two consumers' idempotency, outbox relay, migration, and the five-route/two-event contract groups in §3 are expected to clear ≥70%.

`notification-service` increment: the new category, consumer, and template each have a small, fully-enumerable case set (§6) — expected to comfortably clear all three floors without materially changing that service's already-measured aggregate coverage.

## 8. Fixtures (built, not sourced)

- `tests/fixtures/billing_responses/*.json` (`social-service`) — fixture `billing-service` entitlement-check responses (entitled/unentitled), same shape as `recipe-service`'s existing fixtures (may be copyable/adaptable, not shared code — CLAUDE.md §2.5).
- `tests/fixtures/recipe_events/*.json` (`social-service`) — fixture `RecipePublished`/`RecipeUnpublished` payloads for consumer tests.
- `tests/fixtures/social_events/*.json` (`notification-service`) — fixture `UserFollowed` payloads for the new consumer's tests.
- No real call to `billing-service`, `recipe-service`, or `social-service` anywhere in either suite.
