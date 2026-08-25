# ADR-0023: Per-Service Ownership of Erasable-Data Encryption Keys

## Status
Accepted

## Date
2026-08-25

## Context
`docs/data-protection-and-privacy.md` §4 originally specified that crypto-
shredding for erasable personal data would rely on per-user data keys
"stored in `identity-service`'s key store." That key store never existed:
`identity-service`'s approved implementation plan and its full test suite
(139 tests) contain no key store, no KMS integration, and no
account-deletion endpoint at all -- the doc described a centralized
capability that no plan ever built.

`profile-service` is the first service in the codebase that holds GDPR
Article 9 special-category data requiring crypto-shreddable encryption
(`WeightRecorded.weight_kg`, `BodyMetricRecorded.value`,
`GoalSet`/`GoalUpdated.target_value` -- CLAUDE.md section 8). Its
implementation plan (`/plans/profile-service/implementation-plan.md`,
§9.1) had to resolve this before per-user envelope encryption could be
built at all, since there was no existing centralized store to integrate
with, and no concrete prerequisite plan to build one.

This ADR formalizes that decision (already made and human-approved via the
plan's Addendum 1, §9.1) as a durable, discoverable architectural record,
per `security-agent`'s and `architecture-agent`'s independent conclusion
during `/implementation-review` that a plan-addendum plus a corrected line
in `docs/data-protection-and-privacy.md` was not sufficient visibility for
a decision that changes a documented cross-service design.

Forces at play:
- **No bounded path forward for a centralized store today.** No service
  owns key-store responsibility, and no plan proposes building one.
  Blocking `profile-service` (and every future erasable-data service) on a
  centralized store with no concrete owner or timeline would stall
  indefinitely, not for a bounded period.
- **Consistency with existing per-service ownership elsewhere.** CLAUDE.md
  section 2.5 already mandates "no shared schemas across service
  boundaries" for every other per-service table (event store, outbox,
  processed-inbound-events dedup) -- a shared, centralized key store would
  be the one exception to that principle without a specific justification
  for why key material is different.
- **GDPR erasure still needs to actually work per-service today.**
  `profile-service` needs a working crypto-shredding mechanism now (even
  though the erasure trigger itself is out of scope until an upstream
  `AccountDeletionRequested`-style event exists -- plan §9.2), not a
  design that depends on a capability that doesn't exist.

## Decision
Each event-sourced (or otherwise erasable-personal-data-holding) service
owns its own per-user data-key material, KMS-wrapped (envelope
encryption), in its own database table -- not a centralized,
`identity-service`-owned (or any other single service's) key store.

Concretely: `profile-service` owns `profile_data_keys`
(`services/profile-service/infrastructure/persistence/models.py`),
populated and read exclusively by `KmsEnvelopeDataEncryption`
(`infrastructure/security/kms_envelope_data_encryption.py`). Any future
service that needs to hold erasable personal data (e.g. `diary-service`,
per CLAUDE.md's event-sourcing scope) follows the same pattern: its own
`<service>_data_keys`-shaped table, its own KMS integration, never a
dependency on another service's key table.

This decision originates in
`/plans/profile-service/implementation-plan.md` Addendum 1, §9.1
(resolved option (a) there); this ADR formalizes it as Accepted rather
than re-litigating it.

## Considered Alternatives
- **(a) Per-service key ownership (chosen).** Each service that holds
  erasable personal data owns its own KMS-wrapped per-user key table.
  Ships now, consistent with the existing no-shared-schemas principle,
  smaller KMS/IAM blast radius per service (a compromised service's KMS
  grant only ever exposes that service's own key material). Trade-off: no
  single audit choke-point for "did erasure happen everywhere for this
  user" -- see Consequences.
- **(b) Centralized key store (originally specified, rejected for now).**
  A single service (originally assumed to be `identity-service`) owns all
  per-user key material for every other service. Would give a single
  audit choke-point and a single erasure operation per user, but requires
  building and operating a new shared capability with its own API,
  availability requirements, and blast-radius profile (a compromise of
  the central store threatens every service's encrypted data at once) --
  and today, no plan builds it, no service owns it, and blocking on it has
  no bounded timeline. Rejected for now; may be revisited if/when a
  concrete owner and plan for a centralized store exists (see Consequences
  below).

## Consequences
### Positive
- `profile-service`'s crypto-shredding-ready encryption could ship without
  waiting on an unbuilt, unowned centralized capability.
- Smaller KMS/IAM blast radius per service -- a compromised service's KMS
  grant/IAM role only ever threatens that service's own key material, not
  every service's.
- Consistent with CLAUDE.md section 2.5's existing no-shared-schemas
  principle, applied uniformly rather than carving out an exception for
  key material specifically.
- Each service's erasure logic is self-contained and independently
  testable/operable -- no cross-service synchronous dependency introduced
  into the erasure path.

### Negative / Trade-offs
- A future multi-service erasure flow (once an upstream deletion-trigger
  event exists -- plan §9.2) must coordinate N independent crypto-shred
  operations, one per service holding that user's erasable data, rather
  than a single call to one centralized store. This is inherently a saga
  (ADR-0019), not a single transaction, and must be designed as such when
  that erasure flow is actually built.
- No single audit choke-point for "did erasure happen everywhere for this
  user" -- a future DSAR (Data Subject Access Request) audit needs to
  enumerate every service's own key table individually to confirm
  complete erasure, rather than querying one central record. This must be
  accounted for in `docs/data-protection-and-privacy.md`'s erasure
  checklist and in whatever saga eventually orchestrates cross-service
  erasure.
- Key-rotation policy, KMS grant management, and key-table schema are now
  each service's own responsibility to get right, rather than inheriting
  a single hardened implementation -- more surface area to review per
  service, though also more isolated blast radius per the Positive point
  above.

### Follow-up actions
- `docs/data-protection-and-privacy.md` §4 already reflects per-service
  ownership (corrected alongside the profile-service implementation) --
  updated to reference this ADR as the authoritative decision record
  rather than only the plan addendum.
- Any future service holding erasable personal data (`diary-service`
  being the next concrete candidate, per CLAUDE.md's event-sourcing scope)
  must follow this same per-service-key-table pattern in its own
  implementation plan, citing `profile-service`'s `profile_data_keys` as
  prior art.
- When a concrete cross-service erasure flow is designed (blocked on an
  upstream deletion-trigger event existing -- plan §9.2), it must be
  specified as a saga in `docs/sagas-and-distributed-transactions.md`
  (ADR-0019) that fans out to each service's own crypto-shred operation,
  and the DSAR-audit gap noted above must be addressed there (e.g. an
  aggregated erasure-confirmation record, itself not a single point of
  key-material compromise).

## References
- `/plans/profile-service/implementation-plan.md`, §9.1 and Addendum 1
  (the origin of this decision, human-approved 2026-08-24)
- `docs/data-protection-and-privacy.md` §4 (crypto-shredding mechanism,
  erasure checklist)
- CLAUDE.md section 2.5 (database strategy -- no shared schemas across
  service boundaries) and section 8 (biometric/health data, GDPR Article 9)
- ADR-0002 (CQRS and event sourcing scope -- `profile-service` is
  full-event-sourced, making crypto-shredding rather than row deletion the
  mechanism for erasing event-payload personal data)
- ADR-0019 (saga pattern -- the future cross-service erasure flow's
  required shape)
- `services/profile-service/infrastructure/persistence/models.py`
  (`ProfileDataKeyModel` / `profile_data_keys`)
- `services/profile-service/infrastructure/security/kms_envelope_data_encryption.py`
