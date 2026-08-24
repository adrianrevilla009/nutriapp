# Domain Setup Guide

This repository is a **domain-agnostic template** extracted from a real
nutrition-tracking product. The engineering process, architecture patterns,
and guardrails are reusable as-is. Everything that was specific to
nutrition has been replaced with `{{PLACEHOLDER}}` markers or generic
example names. Do not start `/implementation-plan` on anything until this
checklist is done — the agents will otherwise implement the placeholders
literally or stall asking what they mean.

## 1. Define the product (do this first, outside the repo)

Before touching any file, write down — even briefly, in a scratch doc —
the product-requirements gap this template deliberately does not fill:

- Who is the user, and what is the one core action they repeat most often?
- What are the bounded contexts (domains)? Aim for 3-7 to start. Record
  them in `docs/domain-glossary-and-context-map.md`.
- Does the product have AI-native features (an assistant grounded in user
  data, media/photo recognition)? If not, you will delete two services.
- Does the product handle sensitive personal data (health, financial,
  biometric, children's)? This changes `docs/data-protection-and-privacy.md`
  and `CLAUDE.md` section 8 substantially.
- **Is the product multi-tenant (B2B, teams/organizations) or
  single-tenant (B2C, one account per user)?** This must be resolved as
  ADR-0018 **before** `identity-service`'s data model is implemented —
  see that ADR's own rationale for why it's the one exception to this
  repo's usual "defer until measured need" bias.
- **Does the product need to satisfy a formal compliance framework**
  (SOC 2, HIPAA, PCI-DSS, ISO 27001)? Resolve as ADR-0020 and fill in
  `docs/compliance-mapping.md`. "Not yet" is a valid answer for an early
  product — revisit the moment a customer's procurement process asks.
- Does the product ingest third-party data (scraping, feeds, partner APIs)?
  If not, delete `.claude/skills/external-data-ethics/`.
- **What is the long-term scale ambition, if any?** Fill in ADR-0021 —
  "no specific target beyond standard reliability" is a valid, explicit
  answer.
- User stories and business rules per domain — this template intentionally
  contains **zero product requirements**. Write these before your first
  `/implementation-plan`, e.g. in a new `docs/product-requirements.md`.

## 2. Global find-and-replace

| Placeholder | Replace with |
|---|---|
| `NutriApp` | Your product's name |
| `nutriapp` | Your product's kebab-case slug (namespaces, tags, devcontainer name, Semgrep ruleset path) |
| `{{ONE_LINE_PRODUCT_DESCRIPTION}}` | One line, what it does |
| `{{PRODUCT_ONE_PARAGRAPH_DESCRIPTION ...}}` | Full paragraph, `CLAUDE.md` section 1 |
| `diary-service` | Your primary transactional service's real name |
| `nutrition-calculation-service` | Your derived-computation service's real name, or delete if none |
| `food-recognition-service` | Your media-recognition service's real name, or delete if none |
| `nutrition-assistant-service` | Your AI-assistant service's real name, or delete if none |

Files containing these: `CLAUDE.md`, `ARCHITECTURE.md`, `README.md`,
`docs/events-catalog.md`, and any doc you copy the service table into.

## 3. Rename or delete the example agents

| File | Action |
|---|---|
| `.claude/agents/core-domain-agent.md` | Rename to `<your-core-service>-agent.md`, rewrite its bounded-context description |
| `.claude/agents/transaction-agent.md` | Rename or merge into core-domain-agent if you don't need a separate transactional service |
| `.claude/agents/media-recognition-agent.md` | Rename to match, or **delete** if no media/photo/video recognition |
| `.claude/agents/ai-assistant-agent.md` | Rename to match, or **delete** if no AI assistant |
| `.claude/agents/catalog-agent.md` | Keep if you have reference/catalog data, else delete |
| `.claude/agents/analytics-agent.md`, `notification-agent.md`, `identity-agent.md` | Keep — generic patterns most products need |
| `architecture-agent`, `qa-agent`, `devops-agent`, `infra-agent`, `security-agent`, `reviewer-agent` | Keep as-is — fully domain-agnostic |

## 4. Rename, rewrite, or delete the example skills

| Skill | Action |
|---|---|
| `.claude/skills/domain-calculation-conventions/` | Rewrite with your domain's actual core calculations (pricing, scoring, eligibility, whatever your "nutrition math" equivalent is) |
| `.claude/skills/external-data-ethics/` | Keep if you ingest third-party data, else delete |
| `.claude/skills/media-recognition-conventions/` | Keep if you have media recognition, else delete |
| `.claude/skills/rag-conventions/` | Keep if you have an AI assistant, else delete |
| `.claude/skills/llm-cost-and-model-selection/`, `prompt-engineering-standards/` | Keep only if any service calls an LLM |
| All others (`hexagonal-architecture`, `cqrs-event-sourcing`, `terraform-conventions`, `ci-cd-conventions`, `testing-strategy`, `caching-strategy`, `resilience-patterns`, `database-migrations`, `messaging-conventions`, `api-conventions`, `monorepo-tooling`, `containerization`, `feature-flags`, `i18n-conventions`, `accessibility-standards`, `observability-audit`, `backup-dr`, `supply-chain-security`, `load-testing`, `documentation-standards`, `notification-conventions`, `data-protection`, `code-quality-gates`) | Keep as-is — fully domain-agnostic engineering conventions |
| `.claude/skills/saga-conventions/` | Keep if any feature involves a cross-service business transaction; harmless if unused |
| `.claude/skills/multi-tenancy-conventions/` | Keep only if ADR-0018 selects Option B or C; delete if single-tenant (Option A) |

## 5. Docs to review line-by-line (light domain mentions remain)

These are ~95% generic already but reference the example service names —
do a find-and-replace pass rather than a rewrite:

`docs/api-catalog.md`, `docs/events-catalog.md`, `docs/observability-slo.md`,
`docs/performance-testing.md`, `docs/data-protection-and-privacy.md`,
`docs/adr/0002-cqrs-and-event-sourcing.md`,
`docs/adr/0012-catalog-search-strategy.md` (rename/delete if no catalog),
`docs/adr/0013-product-analytics.md`, `docs/adr/0014-mobile-app-strategy.md`,
`docs/security-and-compliance.md`, `docs/backup-and-disaster-recovery.md`.

## 6. Fill in the scale north star (ADR-0021)

`docs/adr/0021-scale-north-star-and-revisit-triggers.md` already exists
as a process — fill in its actual target and per-service triggers so the
ambition (if any) is tracked rather than lost, without forcing premature
over-engineering into v1. "No specific target" is a valid, explicit entry.

## 7. First implementation

Once sections 1-4 are done (5-6 can happen in parallel with early
development), the next step is unchanged from the original template:
run `/implementation-plan` for `identity-service` — it's the least
domain-specific service and the best reference implementation for the
pattern every other service will follow.
