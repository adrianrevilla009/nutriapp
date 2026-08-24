# Edge: CDN & WAF

Full rationale: ADR-0010. This document covers day-to-day conventions;
Terraform module ownership belongs to `infra-agent` per
`docs/terraform-and-infrastructure.md`.

## 1. What Goes Through CloudFront vs. Direct to ALB

| Content                          | Cache behavior                          | Owner                     |
|------------------------------------|--------------------------------------------|-----------------------------|
| Frontend static bundle (JS/CSS)    | Long TTL, content-hashed filenames         | `frontend/` build pipeline  |
| Per-user media thumbnails              | Short TTL (per-user, signed URL)           | `food-recognition-service`            |
| `/api/*`                            | No cache (pass-through to Kong)            | N/A — always live           |

Any new static asset type added to the frontend follows the content-hash +
long-TTL pattern by default; anything containing user-specific or
frequently-changing data does not get a CDN cache behavior without an
explicit decision recorded here.

## 2. WAF Rollout

1. Attach AWS Managed Rule groups (Core rule set, Known bad inputs, IP
   reputation) in **count mode** in `dev`/`staging` for at least two weeks.
2. `security-agent` reviews count-mode logs for false positives against
   real traffic patterns (legitimate scraping-target verification traffic
   from `catalog-agent`'s manual browser checks, per
   `.claude/skills/external-data-ethics/SKILL.md`, should never be blocked).
3. Switch to **block mode** in `staging` first, then `prod`, each requiring
   the standard promotion approval in `docs/environments-and-promotion.md`.
4. The project-specific rate-based rule on `/api/v1/auth/*` starts at a
   conservative threshold (informed by expected legitimate login volume,
   not a guess) and is tuned the same way.

## 3. Guardrails

- WAF/CloudFront configuration changes follow the same Terraform-only,
  plan-then-human-approval rule as any other infrastructure change
  (CLAUDE.md section 7) — never a console click-through, even for a
  "quick" rule tweak during an incident (see `docs/incident-response.md`
  for the actual incident path, which still goes through this).
- CloudFront is never used to cache anything containing personal data
  (per-user media is the one exception, and only as short-TTL, signed,
  per-user URLs — never publicly cacheable).
