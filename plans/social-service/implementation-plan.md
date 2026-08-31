# Implementation Plan — `social-service`

**Status:** Approved
**Date approved:** 2026-08-31
**Approved by:** human, delegated in-session ("continua de forma autonoma, te dejo que apruebes los planes") — recorded here per CLAUDE.md §6 step 3's requirement that approval be explicit and traceable independently of this conversation.
**Stage:** 2 (Implementation Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Related:** ADR-0001 (hexagonal architecture), ADR-0002 (CQRS/ES scope — event-driven CRUD), ADR-0004 (messaging backbone), ADR-0008 (bff-service never contains business logic), ADR-0015 (billing/entitlements), ADR-0019 (saga pattern), `.claude/agents/social-agent.md`, `.claude/skills/messaging-conventions/SKILL.md`, `.claude/skills/resilience-patterns/SKILL.md`, `docs/domain-glossary-and-context-map.md`, `docs/events-catalog.md`, `docs/sagas-and-distributed-transactions.md`, `/plans/recipe-service/implementation-plan.md` (closest precedent — entitlement-gating pattern), `/plans/notification-service/implementation-plan.md` (precedent for a real, not deferred, new consumer wiring into an already-merged service)

## 1. Scope

Build `social-service` end-to-end: domain → application → infrastructure → tests, plus its Terraform/Helm/CI wiring, reusing shared platform scaffolding. **This initiative also requires a small, coordinated change to the already-merged `notification-service`** (§6) — see the two-PR sequencing note below.

**Bounded context** (CLAUDE.md §2.2, `.claude/agents/social-agent.md`): one-way follow connections between users and a Pro-gated activity feed composed from followed users' published recipes.

**Architecture review (this session, `architecture-agent`, before this plan was written) — six resolved questions:**

1. **Follow semantics: one-way, no approval required.** Already settled in `docs/domain-glossary-and-context-map.md` ("Follow: A one-way connection from one User to another... Not an organizational membership") and corroborated by `docs/events-catalog.md`'s existing single-step `UserFollowed`/`UserUnfollowed` pair (no `FollowRequested`/`FollowAccepted`). Not re-litigated.
2. **Entitlement gating: reuse `recipe-service`'s cache-first/fallback-never-cached pattern verbatim** — local `entitlement_cache` + `processed_entitlement_events` tables fed by consuming `EntitlementGranted`/`EntitlementRevoked`, falling back to `GET /internal/v1/billing/entitlements/{user_id}` (own named circuit breaker `billing_entitlement_check`) only on a cache miss, fallback result never written back. **Scope of the check**: gates the *acting* user (the follower, or the feed viewer) — there is no requirement that the followee be Pro. **Revocation is non-destructive**: `HandleEntitlementRevokedHandler` only flips the cached flag and blocks *new* follow/feed-view actions — it never deletes or hides existing `follows`/`feed_entries` rows, mirroring `recipe-service`'s identical handler and CLAUDE.md §7's guardrail against silent user-data removal. This makes `social-service` the **second** real consumer implementing `ProUpgradeEntitlementPropagation`'s fan-out (`docs/sagas-and-distributed-transactions.md` updated accordingly, §6).
3. **Feed composition: fan-out-on-read via a local `feed_entries` projection, NOT bff-service aggregation.** `social-service` consumes `RecipePublished`/`RecipeUnpublished` into its own minimal local table (`recipe_id`, `author_id`, `title`, `published_at` — never the full recipe, per CLAUDE.md §2.5's "own local copy" convention). `GET /feed` joins this table against the requesting user's own `follows` table (`WHERE author_id IN (followed_user_ids)`), ordered by `published_at DESC`. Rejected alternative: `bff-service` joining "who I follow" against a new bulk recipe-lookup endpoint — this would make `bff-service` perform actual feed-composition decisions (which posts, what order, what visibility), which is domain logic ADR-0008 explicitly forbids `bff-service` from holding, and would require reopening the already-merged `recipe-service` to add an unplanned bulk endpoint. Fan-out-on-read (not fan-out-on-write / no per-follower row copies) also means unfollow takes effect immediately for free (next `GET /feed` simply stops joining that `author_id`) with no per-follower invalidation to manage.
4. **Privacy/visibility: `Recipe.is_published`/`unpublished_at` IS the privacy control — no separate flag needed, no gap.** Confirmed by reading `services/recipe-service/domain/entities/recipe.py`: there is exactly one visibility mechanism. The real enforcement requirement this reveals: `social-service` must consume `RecipeUnpublished` and remove/flag the corresponding `feed_entries` row **synchronously with that consumption**, not on a scheduled recompute — `social-agent.md`'s "must take effect immediately" rule is read as applying to unpublish-driven feed changes, not just follow-relationship changes. **"Blocking" scope note**: `social-agent.md` mentions "blocking/unfollowing must take effect immediately," but no "Block" concept exists anywhere in `docs/domain-glossary-and-context-map.md`, `docs/events-catalog.md`, or `docs/product-requirements.md`. This plan builds **follow/unfollow only** — a user preventing another from following them or seeing their content ("Block") is explicitly out of scope (§ below), and `social-agent.md`'s wording is flagged as imprecise (same category of finding as `recipe-agent.md`'s wording issue noted in the recipe-service plan's §9.1) — recommend a follow-up doc fix, not blocking this plan.
5. **New events, payload shape confirmed:**
   ```
   ### UserFollowed (v1)
   - Producer: social-service
   - Consumers: notification-service (real, §6), analytics-service (documented, not yet implemented)
   - Payload: { "follow_id": "uuid", "follower_id": "uuid", "followee_id": "uuid", "followed_at": "timestamp" }

   ### UserUnfollowed (v1)
   - Producer: social-service
   - Consumers: analytics-service (documented, not yet implemented) -- NOT notification-service
   - Payload: { "follow_id": "uuid", "follower_id": "uuid", "followee_id": "uuid", "unfollowed_at": "timestamp" }
   ```
   `follow_id` (the `follows` row's own primary key) is `aggregate_id`, matching every other service's single-id-per-row convention. Event-driven CRUD confirmed correct (`social-agent.md` already states this; consistent with CLAUDE.md §2.3 restricting mandatory event sourcing to `diary-service`/`profile-service`).
6. **Notification wiring is real, not deferred.** Unlike every other "documented, not yet implemented" consumer in this codebase (`analytics-service`, `nutrition-assistant-service` — deferred *because those services don't exist yet*), `notification-service` is already built and merged. Per its own precedent (`/plans/notification-service/implementation-plan.md` wired a real `diary-service` consumer because `diary-service` already existed at plan time, while correctly deferring `NutrientDeficiencyDetected` since `analytics-service` didn't), this plan requires a real `notification-service` consumer for `UserFollowed` — see §6 for the coordinated-PR sequencing.

**Acceptance criteria:**

1. **`POST /api/v1/social/follows`** (body: `followee_id`) — follow another user. **Pro-gated** (entitlement check on the follower, cache-first per §1.2). Rejects self-follow and an already-existing follow (idempotent — 200 with the existing row, not a duplicate). Publishes `UserFollowed` (v1) via Outbox.
2. **`DELETE /api/v1/social/follows/{followee_id}`** — unfollow. **Pro-gated** (same entitlement check — an unentitled user cannot even unfollow while unentitled; see §9 open question on whether this is the right call). Idempotent (already-not-following is a no-op, no duplicate event). Publishes `UserUnfollowed` (v1).
3. **`GET /api/v1/social/follows/following`** / **`GET /api/v1/social/follows/followers`** — list who the authenticated user follows / who follows them. **Not Pro-gated** — viewing your own connection lists is not the gated feature (only *acting* — follow/unfollow/feed — is gated, consistent with recipe-service's "authoring is free, publish/search is gated" precedent).
4. **`GET /api/v1/social/feed`** — the authenticated user's activity feed (published recipes from followed users, newest first, paginated). **Pro-gated** (feed viewing, cache-first). Never includes an unpublished/removed recipe (enforced by `feed_entries` row removal on `RecipeUnpublished` consumption, §1.4).
5. **Entitlement cache**: `entitlement_cache` + `processed_entitlement_events` tables, `HandleEntitlementGrantedHandler`/`HandleEntitlementRevokedHandler` consuming `billing-service`'s events — structurally identical to `recipe-service`'s implementation (§1.2).
6. **Feed projection consumer**: `HandleRecipePublishedHandler`/`HandleRecipeUnpublishedHandler` consuming `recipe-service`'s events (idempotent by `event_id`) — upsert/remove `feed_entries` rows (§1.3/§1.4).
7. **`notification-service` gains a real `social_events_consumer.py`** consuming `UserFollowed` only, publishing an opt-in, suppressible (`is_transactional=False`) `new_follower` push notification — see §6 for the exact scoped changes to that already-merged service.
8. Coverage: domain ≥ 90%, application ≥ 85%, infrastructure ≥ 70% (CLAUDE.md §3), for **both** `social-service`'s new code and the incremental code added to `notification-service`.

**Explicitly out of scope for this plan:**
- **Blocking** (preventing a specific user from following you or seeing your content) — no such concept exists in the domain glossary, events catalog, or PRD today (§1.4). `social-agent.md`'s "blocking/unfollowing" wording is flagged as imprecise; this plan builds follow/unfollow only.
- Mutual-follow/approval flows (§1.1 — one-way, pre-resolved, not building a request/accept step).
- Any `analytics-service` consumption of `UserFollowed`/`UserUnfollowed`/`RecipePublished`/`RecipeUnpublished` — that service doesn't exist yet, same deferral pattern as every other not-yet-existing consumer.
- Feed content beyond published recipes (e.g. a future "logged a PR/exercise milestone" activity type) — `RecipePublished`/`RecipeUnpublished` are the only feed-source events today; extending feed sources to other event types is a future addition, not this plan.
- A Redis result cache for feed/follow-list reads — deferred until volume justifies it, mirroring `recipe-service`'s identical deferral for its own search feature (its plan §7).
- The CLAUDE.md §8 consent surface ("users connecting with other users... their profile becomes visible to other users") — deferred to the frontend confirmation-step pattern, identical to `recipe-service`'s 2026-08-30 addendum for its own publish-consent surface. Flagged proactively here (per architecture-agent's recommendation) rather than left for `reviewer-agent` to catch after the fact.

## 2. Architectural classification

**Event-driven CRUD** (ADR-0002, confirmed by architecture-agent) — not event-sourced. `Follow` is a conventional row (one per follower/followee pair), `feed_entries` is a simple event-projected read table (same shape as `recipe-service`'s `entitlement_cache` / `notification-service`'s `reminder_schedule`), events published via Outbox as a side effect.

## 3. Files to create or modify

```
services/social-service/
  pyproject.toml, uv.lock, Dockerfile, .dockerignore, README.md, CLAUDE.md
  alembic.ini
  migrations/versions/0001_create_social_tables.py
      # follows (follow_id, follower_id, followee_id, followed_at,
      #   unique constraint on (follower_id, followee_id))
      # feed_entries (recipe_id, author_id, title, published_at)
      # entitlement_cache (user_id, entitled bool, updated_at)
      # processed_entitlement_events (event_id, processed_at)
      # processed_recipe_events (event_id, processed_at) -- idempotency
      #   for RecipePublished/RecipeUnpublished consumption, separate
      #   dedup table from processed_entitlement_events (two independent
      #   consumers, own idempotency ledgers -- mirrors having two
      #   independently-named circuit breakers in recipe-service)
      # outbox
  domain/
    entities/            # Follow
    value_objects/         # FeedEntry (recipe_id, author_id, title, published_at)
    events/                # base.py (own copy), user_followed.py, user_unfollowed.py
    ports/                  # follow_repository_port.py, feed_repository_port.py,
                          # entitlement_cache_repository_port.py,
                          # processed_entitlement_events_repository_port.py,
                          # processed_recipe_events_repository_port.py,
                          # entitlement_check_port.py (billing-service fallback),
                          # outbox_repository_port.py
  application/
    commands/               # follow_user.py, unfollow_user.py,
                          # handle_entitlement_granted.py, handle_entitlement_revoked.py,
                          # handle_recipe_published.py, handle_recipe_unpublished.py
    queries/                 # list_following.py, list_followers.py, get_feed.py
    dto/
    errors.py
  infrastructure/
    http/
      routes/                # follow_routes.py, feed_routes.py, health.py
      schemas/
      dependencies.py         # reuses packages/shared-contracts' centralized
                          # JWT auth dependency
      error_mapping.py         # reuses recipe-service's 402/NOT_ENTITLED
                          # convention verbatim (architecture-agent's
                          # recommendation from the recipe-service review
                          # to promote this repo-wide)
    external/
      billing_entitlement_client.py  # implements EntitlementCheckPort;
                          # own circuit breaker (billing_entitlement_check)
                          # + retry + timeout -- structurally identical to
                          # recipe-service's client of the same name
    persistence/
      models.py, postgres_follow_repository.py, postgres_feed_repository.py,
      postgres_entitlement_cache_repository.py,
      postgres_processed_entitlement_events_repository.py,
      postgres_processed_recipe_events_repository.py,
      postgres_outbox_repository.py
    messaging/
      billing_events_consumer.py   # EntitlementGranted, EntitlementRevoked
      recipe_events_consumer.py    # RecipePublished, RecipeUnpublished
      rabbitmq_event_publisher.py, outbox_relay_worker.py
    composition_root.py, main.py
  tests/
    unit/domain/            # Follow/FeedEntry value object validation
    unit/application/        # all handlers, mocked ports -- including
                          # self-follow rejection, idempotent
                          # follow/unfollow, entitlement cache-hit/miss/
                          # fallback cases, unentitled-user-rejected
                          # cases, feed excludes unpublished recipes
    integration/infrastructure/  # testcontainers Postgres/RabbitMQ,
                          # BillingEntitlementClient against a fixture
                          # HTTP server (circuit-breaker matrix),
                          # repository round-trips, outbox relay,
                          # migration, both consumers' idempotency
    contract/http/         # all 5 routes, both new event payload contracts

services/notification-service/    # SEE §6 -- small, coordinated addition
    domain/value_objects/notification_category.py   # add "new_follower"
        to PUSH_CATEGORIES
    infrastructure/messaging/social_events_consumer.py   # new, consumes
        UserFollowed only
    infrastructure/templating/templates/push/new_follower_v1.json.j2  # new
    tests/  # unit test for the new category, integration test for the
        new consumer's idempotency, contract test for the template

infra/terraform/environments/dev/social-service.tf   # mirrors
    recipe-service.tf's structure (own RDS schema/user, ECR repo,
    scoped IAM read access to billing-service's internal_reveal_credential
    secret ARN, same pattern)
infra/k8s/charts/social-service/     # own chart, correct env-list format +
    envFrom wiring from the start
.github/workflows/social-service-ci.yml   # mirrors the other services'
    pipelines, pinned uv/action SHAs per existing convention

docs/events-catalog.md     # UserFollowed/UserUnfollowed fleshed out with
    Status/payload (currently under-specified, no payload shown);
    RecipePublished/RecipeUnpublished consumer lists gain social-service
docs/api-catalog.md        # add the 5 new routes, note which are Pro-gated
docs/domain-glossary-and-context-map.md   # add social-service's
    relationships: Open Host Service consumer of billing-service's
    entitlement events + internal endpoint (same classification as
    recipe-service's), Customer-Supplier consumer of recipe-service's
    RecipePublished/RecipeUnpublished, and the new
    social-service -> notification-service relationship (Customer-Supplier
    via UserFollowed)
docs/sagas-and-distributed-transactions.md  # ProUpgradeEntitlementPropagation:
    note social-service is the SECOND real consumer implementing its
    side of the saga's fan-out
ARCHITECTURE.md            # verify any existing social-service
    placeholder is still accurate
docker-compose.yml         # add a social-service block, own database
```

## 4. Ports/adapters affected

**New ports (`social-service`):** `FollowRepositoryPort`, `FeedRepositoryPort`, `EntitlementCacheRepositoryPort`, `ProcessedEntitlementEventsRepositoryPort`, `ProcessedRecipeEventsRepositoryPort`, `EntitlementCheckPort` (→ `billing-service`'s existing internal endpoint), `OutboxRepositoryPort`. No existing port from another service is reused (each service keeps its own port/adapter copy, per CLAUDE.md §2.5); `packages/shared-contracts`' centralized JWT auth dependency is reused for the public routes.

**`notification-service` (existing ports, no new port needed):** the new `social_events_consumer.py` is a new *adapter* implementing the existing consumer pattern already used by `diary_events_consumer.py`/`identity_events_consumer.py` — no new port required, this is additive infrastructure only, consistent with how that service already scales to new event sources.

## 5. Domain events

**Published (`social-service`):** `UserFollowed`, `UserUnfollowed` (both v1, fleshed out from `docs/events-catalog.md`'s existing under-specified entry per §1.5's payload shapes).

**Consumed (`social-service`):** `EntitlementGranted`, `EntitlementRevoked` (v1, `billing-service`) — second real consumer of the `ProUpgradeEntitlementPropagation` saga's fan-out. `RecipePublished`, `RecipeUnpublished` (v1, `recipe-service`) — first real consumer of either event; `docs/events-catalog.md`'s consumer lists for both gain `social-service`.

**Consumed (`notification-service`, §6):** `UserFollowed` (v1, `social-service`) — real, live wiring, not deferred (§1.6).

## 6. Cross-service impact — two coordinated PRs

**This is a two-service initiative**, unlike every prior Phase 2 plan (`billing-service`, `recipe-service`, `activity-service`), which touched exactly one new service plus documentation-only entries elsewhere. Three separate cross-service consumer surfaces are introduced (entitlement events, recipe events, and `notification-service`'s new consumer) — more surface area than any prior single-service plan, so each is enumerated explicitly here rather than left implicit:

1. `social-service` → `billing-service`: consumes `EntitlementGranted`/`EntitlementRevoked` (async) + synchronous fallback call to the existing internal endpoint (§1.2). No `billing-service` code changes.
2. `social-service` → `recipe-service`: consumes `RecipePublished`/`RecipeUnpublished` (async). No `recipe-service` code changes — both events are already `Active` and already publish today; `social-service` is simply a new subscriber.
3. `notification-service` gains a real consumer of `social-service`'s `UserFollowed` (async). **This is the one real code change to an already-merged service.**

**Sequencing (recommended, mirrors the `billing-service`→`recipe-service` precedent of a small preceding/parallel PR against an already-existing dependency rather than one PR straddling two service boundaries):**
- **PR A (small, notification-service only):** add `"new_follower"` to `PUSH_CATEGORIES`, the new `social_events_consumer.py`, the new push template, and their tests. This PR has no dependency on `social-service` existing yet — `UserFollowed`'s payload shape (§1.5) is fully specified here, so the consumer can be built and tested against a fixture event before `social-service` itself is built, exactly as `notification-service`'s original plan built its `diary_events_consumer.py` against `diary-service`'s already-documented contract.
- **PR B (`social-service` itself):** everything in §3's `services/social-service/` tree. Depends on PR A being merged first (or merged alongside, flagged explicitly per the `recipe-service`/`billing-service` precedent) so that once `social-service` starts publishing `UserFollowed` for real, a live consumer already exists rather than a window where the event is published with nothing listening.

No other service's code changes as a result of this plan.

## 7. Resilience/caching/migration needs

- **Circuit breaker**: `billing_entitlement_check` (the cache-miss fallback only) — named, `tenacity` retry, explicit timeout, dedicated `httpx.AsyncClient`, per `resilience-patterns/SKILL.md`. No synchronous call to `recipe-service` anywhere (feed composition is entirely async via consumed events, §1.3) — no `recipe_*` circuit breaker needed, unlike `recipe-service`'s own two-breaker design.
- **Caching**: `entitlement_cache` and `feed_entries` are themselves Postgres-backed projections, not a Redis cache — consistent with `recipe-service`'s/`notification-service`'s precedent of not introducing Redis for a low-volume, already-indexed-lookup use case at this stage (§1's "out of scope" list).
- **Migration**: one initial Alembic migration in `social-service` creating five new tables, purely additive (new service). In `notification-service`: **no migration needed** — `PUSH_CATEGORIES` is a domain-layer `frozenset[str]` validated against a free-text `String(32)` column (confirmed by reading `infrastructure/persistence/models.py` and `notification_category.py` at plan-writing time), and `get_notification_preferences.py` derives default preference rows dynamically from `PUSH_CATEGORIES` — adding `"new_follower"` requires no schema change.

## 8. Test plan reference

`/test-plan` will define concrete test cases next: value object validation, all seven `social-service` command/query handlers (including self-follow rejection, idempotent follow/unfollow, cache-hit/cache-miss-fallback entitlement cases, unentitled-user-rejected-not-degraded, feed correctly excludes an unpublished recipe), the `BillingEntitlementClient`'s circuit-breaker matrix, repository round-trips, outbox atomicity, both consumers' idempotency (`billing_events_consumer`, `recipe_events_consumer` — two independent idempotency ledgers), contract tests for all five routes and both event payloads — plus, in `notification-service`: the new category's validation, the new consumer's idempotency, and the new template's contract test. Not enumerated further here.

## 9. Risks and open questions

1. **Should unfollow require entitlement?** This plan (§1's acceptance criterion 2) gates unfollow the same as follow — an unentitled user who was Pro when they followed someone cannot unfollow them after downgrading, until they either re-upgrade or use billing-service's own cancellation flow (which doesn't touch social-service data at all, per §1.2's "revocation is non-destructive" rule — the follow relationship simply persists). This is a real, debatable product decision: an alternative is to make unfollow *always* available regardless of entitlement (a user should always be able to disengage, even without Pro), which would make it asymmetric with follow. **Recommendation**: keep unfollow gated for this MVP (simpler, one gating rule for the whole "acting" surface, consistent with §1.2's "gates the acting user" framing applied uniformly) but flag this explicitly as a debatable call worth revisiting with real user feedback post-launch, not a silently-buried assumption.
2. **`social-agent.md`'s "blocking" wording is imprecise** (architecture-agent's finding, §1.4) — recommend a small follow-up doc fix for clarity, not blocking this plan, mirroring the identical `recipe-agent.md` wording issue already noted (and left as a non-blocking follow-up) in the recipe-service plan's §9.1.
3. **Two-PR sequencing (§6) is a new pattern** for this codebase — every prior Phase 2 plan touched exactly one new service. If PR A (`notification-service`) and PR B (`social-service`) are not both approved together, `social-service`'s own PR should not merge until PR A has, so `UserFollowed` is never live with zero consumers even transiently. Flagged explicitly, not assumed.
4. No other open questions — the six architecturally significant questions (follow semantics, entitlement pattern, feed composition, privacy enforcement, event shape, notification wiring) were resolved by `architecture-agent` before this plan was written (§1).
