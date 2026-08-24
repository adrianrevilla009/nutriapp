# Onboarding

A practical "start here and actually get productive" runbook, distinct
from `README.md` (which maps the repository) and `CLAUDE.md` (which
defines the rules). This document is for a new human contributor or a
fresh Claude Code session that has never touched this repo before.

## 1. For a New Human Contributor

1. Read `README.md`, then `CLAUDE.md` in full — the domain-instantiation
   pass described in `DOMAIN-SETUP.md` is already complete for NutriApp,
   and CLAUDE.md is the single source of truth everything else assumes
   you've read.
2. Read `docs/domain-glossary-and-context-map.md` — every domain term
   used elsewhere assumes this vocabulary.
3. Set up the local environment: `docker-compose.yml` and `.env.example`
   do not exist yet (CLAUDE.md section 14 — specification phase only).
   Once `devops-agent` scaffolds them per the pipeline in CLAUDE.md
   section 6, this step becomes: clone, copy env file, `docker-compose
   up`, run migrations. Update this step with the actual commands in the
   same change that introduces them.
4. Read the ADRs in `docs/adr/` in order — they explain *why*, not just
   *what*, and reading CLAUDE.md without them means missing the
   reasoning behind non-obvious choices (e.g. why RabbitMQ over Kafka,
   why no service mesh).
5. Pick a small, well-scoped first task and run it through the full
   human-in-the-loop pipeline (CLAUDE.md section 6) once, end to end,
   before taking on anything larger — the pipeline itself has a learning
   curve independent of the codebase.

## 2. For a Fresh Claude Code Session / New Agent

An agent starting cold on this repo (no prior conversation history)
should, before writing any plan:
1. Read `CLAUDE.md` in full.
2. Read the specific agent definition file in `.claude/agents/` matching
   the task at hand, and every skill it references.
3. Check `docs/project-status-tracking.md` (or run `/project-status`) to
   understand what is actually implemented versus still just specified —
   CLAUDE.md section 14 makes clear the spec and the implementation are
   not the same thing, and this is easy to forget mid-session.
4. Check `docs/domain-glossary-and-context-map.md` before introducing any
   new entity, event, or field name, to avoid inventing a synonym for an
   already-defined term.
5. Never skip a human-in-the-loop gate (CLAUDE.md section 6) because a
   session is "just exploring" — exploration that produces a plan or a
   diff is still subject to the same gates once it becomes a real
   change.

## 3. Common First-Task Pitfalls

- Assuming a service exists (or is in scope for the phase being worked
  on) without checking `docs/product-requirements.md`'s Phase 1/Phase 2
  split — not every service in CLAUDE.md section 2.2 is meant to be
  implemented first.
- Assuming CQRS/event sourcing for a service where CLAUDE.md section 2.3
  doesn't mandate it — check the section before assuming the pattern
  applies uniformly.
- Writing an authorization check as an afterthought rather than as an
  explicit step in the command/query handler — see
  `docs/authorization-model.md` section 3.
- Introducing a cross-service call chain without checking whether it
  constitutes an undocumented saga per
  `docs/sagas-and-distributed-transactions.md`.

## 4. Where to Ask

NutriApp is currently a solo project — ask the maintainer directly. If a
team forms later, replace this with the actual channel (Slack, GitHub
Discussions, etc.) in the same change that changes the team structure;
this section is never left blank.

## 5. Ownership

Kept current by whoever last onboarded using it — if a step in this
document was wrong or missing when you followed it, fixing this document
is part of finishing the onboarding, not a separate follow-up task.
