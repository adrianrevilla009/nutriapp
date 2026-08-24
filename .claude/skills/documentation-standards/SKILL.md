---
description: Documentation conventions for NutriApp services — README structure, event catalog updates, and ADR triggers. Use whenever finishing a feature that should update project documentation.
---

# Documentation Standards — Implementation Conventions

Full rationale in `docs/documentation-standards.md`.

## When to Update What

| Change made                                      | Update required                                  |
|-----------------------------------------------------|------------------------------------------------------|
| New or changed public API endpoint                  | Nothing manual — FastAPI regenerates OpenAPI automatically; verify it renders correctly |
| New or changed domain event                          | `docs/events-catalog.md` entry, in the same PR         |
| New external dependency with a resilience pattern     | That service's `README.md`, "External dependencies" section |
| New service scaffolded                                | New `README.md` for that service, add it to `ARCHITECTURE.md`'s service map |
| Decision changing stack/boundaries/messaging/testing   | New ADR via `/adr`, following `docs/adr/template.md`    |

## Service README Template
```markdown
# <service-name>

## Purpose
<one paragraph>

## How to run locally
<exact commands>

## How to test
- Unit: <command>
- Integration: <command>
- Contract: <command>
- E2E: <command>

## Owned events
- <EventName> (v<n>) — see docs/events-catalog.md

## Consumed events
- <EventName> from <service> — why

## External dependencies
- <dependency>: circuit breaker (fail_max=<n>, reset_timeout=<n>s), retry
  (<policy>), fallback: <behavior>
```

## Docstring Convention
Document the *why*, not the *what* (the code should already make the "what"
clear through naming):
```python
def calculate_core_metric(profile: UserProfile) -> Result:
    """<Named method/standard the formula is based on>. Chosen over <alternative> for better
    accuracy for this use case (see docs/adr for the formula
    rationale if one exists, otherwise cite the source directly here)."""
```

## Rules
- Never leave a new domain event undocumented in `docs/events-catalog.md` —
  `reviewer-agent` blocks on this.
- Never let a service's `README.md` describe a "how to test" command that no
  longer works — treat doc drift as a bug.
