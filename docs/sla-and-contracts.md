# SLAs & External Contracts

`docs/observability-slo.md` defines **internal** SLOs — targets the team
holds itself to, with an internal error-budget policy. This document
covers the separate question of what, if anything, is **contractually
promised to external customers** — the two must never be silently
conflated, because an SLA is a legal/commercial commitment with
consequences (credits, termination rights), while an SLO is an
engineering discipline tool.

## 1. Do You Have External SLAs? (answer explicitly)

**No external SLA.** ADR-0015 (Accepted) makes NutriApp a paid product
(freemium with a Pro subscription tier), but it is a B2C consumer product
with no enterprise tier or negotiated contract — the Pro subscription
grants feature access, not a contractual uptime commitment. This is
revisited if a future B2B/enterprise offering is introduced (which would
also revisit ADR-0018's single-tenant decision).

## 2. Relationship Between SLA and SLO

**An external SLA must always be set looser than the internal SLO it is
backed by** — never equal, never tighter. Example: if `identity-service`'s
internal SLO (`docs/observability-slo.md`) is 99.9% availability, an
external SLA promising 99.9% leaves zero error budget for anything that
isn't itself an SLA breach (a deploy issue, a dependency outage) — the
internal target must have headroom the external promise doesn't need to
know about.

| Service / capability | Internal SLO (from `docs/observability-slo.md`) | External SLA | Headroom |
|---|---|---|---|
| Core API availability | See `docs/observability-slo.md` | None (see section 1) | N/A |

## 3. SLA Credits & Remediation

N/A — no external SLA exists (section 1), so no credit/remediation policy
is needed. If an enterprise tier with a contractual SLA is introduced
later, this section must be filled in before that tier ships, using
`docs/observability-slo.md`'s existing Prometheus/Grafana stack as the
sole source of truth for measuring a breach — never a separate ad-hoc
measurement invented for the SLA. This is a business decision, not
something an agent should decide unilaterally —
`security-agent`/`architecture-agent` can flag when monitoring shows an
SLA-relevant breach, but issuing a credit requires human sign-off.

## 4. Data Processing Terms (if applicable)

If the product processes data on behalf of a business customer (B2B), a
Data Processing Agreement (DPA) is typically a contractual requirement
distinct from the vendor-side DPAs already covered in
`docs/data-protection-and-privacy.md` section 3 — that section covers
*this product* as a data controller/processor of *its own* vendors; this
section covers *this product's customer* as the controller and *this
product* as their processor. Track any customer-specific DPA terms that
impose engineering requirements (specific data residency, specific
retention overrides) here, and cross-reference
`docs/multi-region-strategy.md` / `docs/multi-tenancy.md` if a specific
customer's contract requires isolation beyond the platform default.

## 5. Status Page & Incident Communication

If any external SLA exists, a public or customer-facing status page
(reporting the same incidents tracked internally per
`docs/incident-response.md`) is expected by customers as a matter of
course — decide here whether this is a simple static page updated
manually during an incident, or an automated status page tied to the
Prometheus Alertmanager routing already defined in
`docs/observability-slo.md` section 4.

## 6. Ownership

Human-owned, not delegated to an agent: any change to what is
contractually promised to a customer requires the same explicit human
approval as a destructive infrastructure action (CLAUDE.md section 7),
since unlike an internal SLO, a wrong SLA promise has legal and financial
consequences. Agents may propose SLA language based on measured
capability (`docs/observability-slo.md` data) but never accept it on the
human's behalf.
