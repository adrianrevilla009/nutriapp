---
description: Detailed conventions for implementing Hexagonal Architecture (Ports & Adapters) in NutriApp services. Use whenever creating or modifying domain, application, or infrastructure layer code in any service.
---

# Hexagonal Architecture — NutriApp Conventions

Full rationale in `docs/adr/0001-hexagonal-architecture.md`. This skill is the
implementation-level detail.

## Layer Rules

### Domain layer (`domain/`)
- Pure Python only. No imports of FastAPI, SQLAlchemy, Pydantic, RabbitMQ
  clients, or any other framework/infrastructure library.
- Contains: Entities (objects with identity), Value Objects (immutable,
  compared by value — e.g. `Quantity`, `<DomainValueObject>`), Aggregates (a
  cluster of entities with a single root enforcing invariants), Domain Events
  (facts that happened), Domain Services (stateless operations that don't
  naturally belong to a single entity), and Ports (interfaces the domain or
  application layer needs, defined here or in `application/` depending on who
  consumes them).
- Ports are Python `Protocol` classes (structural typing, no need to inherit):
  ```python
  from typing import Protocol

  class ItemRepositoryPort(Protocol):
      async def get_by_id(self, item_id: str) -> Item | None: ...
      async def save(self, item: Item) -> None: ...
  ```

### Application layer (`application/`)
- Orchestrates use cases via Command and Query handlers.
- Depends only on domain objects and on ports (never on a concrete adapter).
- Commands express intent to change state (`<Verb><Aggregate>Command`); Queries express
  a read (`Get<Summary>Query`). Each has exactly one handler.
- DTOs (Data Transfer Objects) here convert between the HTTP/messaging layer's
  shapes and domain objects — the domain never sees a raw HTTP request or a
  raw DB row.

### Infrastructure layer (`infrastructure/`)
- Implements ports as concrete adapters: `Postgres<Aggregate>Repository implements
  <Aggregate>RepositoryPort`, `RabbitMqEventPublisher implements EventPublisherPort`.
- Contains HTTP controllers (thin — parse request, call an application
  handler, serialize response, no business logic), DB access code, message
  broker clients, external API clients.
- Wiring (which concrete adapter satisfies which port) happens here or in a
  small composition-root module, using the project's DI library (`punq` or
  `dependency-injector`).

## Dependency Direction
```
infrastructure --> application --> domain
```
Never the reverse. If you find yourself importing an infrastructure module
from `domain/` or `application/`, that is an architecture violation —
`architecture-agent` will flag it in review.

## Testing Implications
- Domain: unit tests with no mocking of the domain itself, no I/O.
- Application: unit tests using fake/in-memory implementations of ports (not
  the real adapters).
- Infrastructure: integration tests against real (containerized) dependencies.

See `.claude/skills/testing-strategy/SKILL.md` for the full testing approach.

## Enforcement
Consider adding `import-linter` (or equivalent) configuration per service to
fail CI automatically if a domain-layer module imports anything outside the
standard library or other domain modules.
