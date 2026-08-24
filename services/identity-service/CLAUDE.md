# identity-service — agent-scoped notes

This file is scoped guidance for any agent working inside
`services/identity-service/`. It does not replace the root `/CLAUDE.md`
(architecture, workflow, guardrails) or `.claude/agents/identity-agent.md`
(bounded context, domain responsibilities, rules) — read both first.

## Quick orientation

- Hexagonal layout: `domain/` -> `application/` -> `infrastructure/`,
  dependencies point inward only (ADR-0001).
- Conventional persistence + Outbox (ADR-0002, CLAUDE.md section 2.4) —
  not event-sourced.
- Token signing scheme: ADR-0022 (RS256 access tokens, revocable opaque
  refresh tokens). Any change to this scheme needs a new ADR, not an
  in-place edit.
- Never log a password, password hash, or raw token — see
  `domain/entities/audit_record.py`'s forbidden-metadata-key guard for the
  audit trail specifically.
- The internal reveal endpoint (`infrastructure/http/routes/internal_token_routes.py`)
  is the only inbound synchronous dependency this service has; it is never
  routed through Kong and must stay off the public API catalog surface.

## Where things live

- Ports: `domain/ports/*.py` (Python `Protocol`s).
- Adapters: `infrastructure/persistence/`, `infrastructure/security/`,
  `infrastructure/cache/`, `infrastructure/messaging/`.
- Composition root: `infrastructure/composition_root.py` — the only place
  concrete adapters are wired to ports.
- Tests mirror `testing-strategy` SKILL.md's layout under `tests/`.
