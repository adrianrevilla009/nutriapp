# ADR-0010: CloudFront (CDN) and AWS WAF at the Edge

## Status
Accepted

## Date
2026-08-23

## Context
ADR-0008 places Kong immediately behind the ALB for API-level concerns
(rate limiting per client, JWT validation, CORS). Two problems sit in front
of that boundary, neither of which Kong is the right tool for:
1. **Static asset delivery** — the Next.js frontend's static bundle and
   per-user media thumbnails (`food-recognition-service` output, per
   `.claude/skills/media-recognition-conventions/SKILL.md`) currently have no
   caching/edge-delivery layer, meaning every asset request round-trips to
   `origin` (the ALB) even though most of this content is either fully
   static or cacheable per-user for short windows.
2. **Network-layer/L7 abuse before it reaches any application component** —
   Kong rate-limits per authenticated client, but a volumetric or
   bot-driven attack against public, unauthenticated endpoints (login,
   registration, public catalog search) benefits from being absorbed at
   the edge, before it consumes ALB/EKS capacity at all.

## Decision
Add **Amazon CloudFront** in front of the ALB, with **AWS WAF** attached to
the CloudFront distribution:
- CloudFront caches the frontend's static bundle and per-user media thumbnails
  by cache-control headers the owning service sets; all API traffic
  (`/api/*`) is configured with a pass-through (no-cache) behavior so Kong
  and the application layer remain the source of truth for anything
  dynamic.
- AWS WAF uses the **AWS Managed Rules** free-tier-eligible rule groups
  (Core rule set, Known bad inputs, IP reputation list) plus a
  project-specific rate-based rule on `/api/v1/auth/*` — a second,
  network-layer line of defense in front of the application-layer rate
  limiting Kong already does per ADR-0008, not a replacement for it.
- Both are provisioned by Terraform, same as every other AWS resource
  (ADR-0006), never configured by hand in the console.

## Considered Alternatives
- **Cloudflare (CDN + WAF + DDoS)** — stronger DDoS absorption at greater
  scale and a more mature bot-management product, but introduces a second
  cloud vendor and DNS/cert coordination outside the existing AWS-only
  stack (ADR-0006, ADR-0007). Rejected for now to keep the infrastructure
  surface single-vendor; revisit via a new ADR if traffic/attack volume
  outgrows what CloudFront + WAF handles.
- **No CDN/WAF, rely on Kong + ALB security groups only** — what the
  project has today. Rejected: leaves static-asset delivery uncached
  (unnecessary origin load and latency) and leaves public unauthenticated
  endpoints with only application-layer, not network-layer, abuse
  protection.
- **Self-hosted edge (e.g. Varnish) instead of CloudFront** — avoids a
  managed-service cost, but reintroduces exactly the kind of
  undifferentiated infrastructure toil `docs/cost-management.md` and
  ADR-0006 already argue against taking on manually when a managed
  equivalent is inexpensive at this scale.

## Consequences
### Positive
- Static asset and thumbnail latency drops for repeat visitors; ALB/EKS
  origin load drops correspondingly.
- A first line of defense against volumetric/bot abuse exists before any
  request reaches application infrastructure.

### Negative / Trade-offs
- One more Terraform-managed resource and one more place cache invalidation
  can go stale (mitigated by cache-busting via content-hashed filenames for
  the frontend bundle, and short TTLs for thumbnails).
- WAF managed rules can false-positive on legitimate traffic; start in
  **count mode** for two weeks per environment before switching to **block
  mode**, per the rollout note in `docs/edge-and-cdn.md`.

### Follow-up actions
- Add CloudFront + WAF Terraform module to `infra/terraform/` when
  infrastructure work begins (see `docs/terraform-and-infrastructure.md`).
- Document cache-control conventions per asset type in
  `docs/edge-and-cdn.md` (done) and `docs/frontend-architecture.md`.

## References
- `docs/edge-and-cdn.md`
- ADR-0006, ADR-0008
