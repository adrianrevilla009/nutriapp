# Implementation Plan — Foundational Platform Infrastructure (pre-`identity-service`)

**Status:** Approved
**Date approved:** 2026-08-24
**Stage:** 2 (Implementation Plan) of the human-in-the-loop pipeline, CLAUDE.md section 6
**Related:** `/plans/identity-service/implementation-plan.md`

Stage 2 of the human-in-the-loop pipeline. **No files were created or
edited as part of drafting this plan** — every `.tf` file, module, and
Helm chart below is written in a later, separately-approved
`/implementation-execution` step, and even then only a `terraform plan`
output is produced for human review; **no agent runs `terraform
apply`/`terraform destroy`**, enforced by
`.claude/hooks/pre-terraform-guard.sh` and CLAUDE.md §7.

## 1. Scope

Provision the shared platform layer that every future service (starting
with `identity-service`) needs to deploy to `dev`. Not
identity-service-specific — the reusable foundation identity-service's own
plan builds on.

In scope (per `docs/terraform-and-infrastructure.md` §1 module list):
1. `infra/terraform/bootstrap/` — S3 remote-state bucket + DynamoDB lock table, one-time manual apply.
2. `infra/terraform/modules/vpc/` — 3-AZ VPC, public (ALB/NAT only) + private (EKS/RDS/ElastiCache/RabbitMQ-ready) subnets.
3. `infra/terraform/modules/eks/` — EKS cluster, on-demand + spot managed node groups, IRSA/OIDC provider, cluster-autoscaler IAM scaffolding. **API endpoint access: public+private, public side restricted via `cluster_endpoint_public_access_cidrs` to the operator's IP** (resolved decision — simpler for solo/dev work than a permanent bastion/VPN; the CIDR allowlist needs periodic updates as the operator's IP changes).
4. `infra/terraform/modules/rds/` — one shared PostgreSQL instance for all services, `manage_master_user_password = true` (RDS-managed secret, never a plaintext value in Terraform state).
5. `infra/terraform/modules/elasticache/` — single-node Redis for `dev`.
6. `infra/terraform/modules/secrets/` — Secrets Manager baseline + IRSA IAM policies, including identity-service's JWT signing key pair and DB credential secret containers.
7. `infra/terraform/environments/dev/` — thin composition of the above, dev-sized.
8. `infra/k8s/charts/_lib/` — shared Helm library chart (Deployment, Service, HPA, PDB, NetworkPolicy, ServiceAccount+IRSA, standard probes).
9. Namespace convention: single `nutriapp-dev` namespace (+ its default-deny NetworkPolicy), not per-service.
10. **Dev scale-to-zero** (per `docs/cost-management.md` §1), folded into this plan's scope rather than deferred: a scheduled Lambda/EventBridge rule that scales EKS node groups to zero and stops the RDS instance outside working hours.

**Explicitly out of scope** (follow-up work, not silently dropped):
- `staging`/`prod` environments.
- `modules/messaging/` (RabbitMQ), `modules/qdrant/`, `modules/observability/`, `modules/dns-and-tls/` — not needed for identity-service's first deploy; VPC private subnets are still sized/tagged to accommodate them later.
- Installing cluster-wide controllers (cluster-autoscaler, AWS Load Balancer Controller, External Secrets Operator) as running workloads — this plan provisions their **IAM/IRSA scaffolding** only; the actual `helm install` is `devops-agent` CI/CD territory, follow-up.
- `infra/k8s/charts/identity-service/` — owned by identity-service's own plan.

Acceptance criteria: once approved, later implemented, and applied by a
human, `identity-service`'s own Terraform scope (its variables file +
Helm chart) can be added on top of this layer without needing any
additional platform-level resources.

## 2. Architectural classification

Not a hexagonal service — infrastructure code. Layer breakdown instead:
- **Terraform**: environment-agnostic modules (`vpc`, `eks`, `rds`, `elasticache`, `secrets`) + one thin environment composition (`environments/dev/`).
- **Kubernetes/Helm**: one shared library chart only (`_lib`); no service chart touched.
- **Bootstrap**: a standalone root module outside the environment/module split (chicken-and-egg for remote state).

## 3. Files to create or modify

**Terraform — bootstrap** (local state, applied once manually by the human, never by an agent):
- `infra/terraform/bootstrap/{main,variables,outputs,versions}.tf`
- `infra/terraform/bootstrap/README.md` — exact one-time manual `init`/`plan`/`apply` steps; state stays local/gitignored, operator keeps a personal backup of the state file since losing it would orphan the S3 bucket/DynamoDB table from Terraform's tracking (recoverable via `terraform import`).

**Terraform — modules:**
- `infra/terraform/modules/vpc/{main,variables,outputs,versions}.tf`
- `infra/terraform/modules/eks/{main,variables,outputs,versions,iam,node_groups}.tf`
- `infra/terraform/modules/rds/{main,variables,outputs,versions}.tf` — the one shared instance, param group, subnet group.
- `infra/terraform/modules/elasticache/{main,variables,outputs,versions}.tf`
- `infra/terraform/modules/secrets/{main,variables,outputs,versions,iam}.tf`
- `infra/terraform/modules/scale-to-zero/{main,variables,outputs}.tf` — EventBridge schedule + Lambda to scale node groups to zero and stop RDS outside working hours (dev only).

**Terraform — environment:**
- `infra/terraform/environments/dev/{main,variables,outputs,providers,backend}.tf`
- `infra/terraform/environments/dev/terraform.tfvars` — dev sizing only, no secret values.
- `infra/terraform/README.md` — points to `docs/terraform-and-infrastructure.md`, documents module dependency order.

**Kubernetes:**
- `infra/k8s/charts/_lib/Chart.yaml` (`type: library`)
- `infra/k8s/charts/_lib/templates/_deployment.tpl`, `_service.tpl`, `_hpa.tpl`, `_pdb.tpl`, `_networkpolicy.tpl`, `_serviceaccount.tpl` (IRSA annotation), `_probes.tpl`
- `infra/k8s/charts/_lib/templates/_db-provision-job.tpl` — **new**, a Helm-hook Job template (pre-install/pre-upgrade) that a consuming service chart uses to create its own logical database + role inside the shared RDS instance, running from inside the cluster (see §9.1). This is the reusable mechanism identity-service's chart calls.
- `infra/k8s/charts/_lib/values.schema.json` — enforces `resources.requests`/`resources.limits` presence at lint time.
- `infra/k8s/charts/_lib/README.md` — how a consuming service chart (e.g. identity-service's) includes these named templates, including the DB-provisioning Job pattern.

No `docs/*.md` content changes anticipated, except a note added to
`docs/cost-management.md` documenting the scale-to-zero schedule once
implemented.

## 4. Ports/adapters affected

Not applicable — no hexagonal service code is touched. Closest analogue:
this plan defines the module boundary contract (module inputs/outputs)
and the Helm `_lib` chart's named-template contract every future service
chart consumes, including the new DB-provisioning Job pattern.

## 5. Domain events

Not applicable — infrastructure only.

## 6. Cross-service impact

Maximally cross-cutting even though only one service (identity-service)
consumes it today:
- `architecture-agent` review recommended before implementation.
- Direct coordination point with identity-service's plan: both touch
  `infra/terraform/environments/dev/main.tf`. This plan adds the module
  calls for `vpc`, `eks`, `rds` (shared instance), `elasticache`,
  `secrets` (baseline), the scale-to-zero schedule, and the
  namespace/NetworkPolicy resources. Identity-service's plan adds its own
  Helm release, which invokes the `_db-provision-job` template from
  `_lib` at install time rather than a Terraform-level database resource
  (see §9.1).
- The `secrets` module provisions identity-service's JWT signing key pair
  (`tls_private_key` resource, stored to Secrets Manager, never a literal
  value in `.tf`/`.tfvars`) and DB credential secret container here, per
  the original task scope — identity-service's plan references these
  outputs rather than recreating them.
- Every future service reuses the same `vpc`/`eks`/`elasticache` modules
  unchanged and the same `_db-provision-job` Helm pattern for its own
  logical database — no further platform-layer Terraform changes needed
  for the next several services.

## 7. Resilience/caching/migration needs

- No circuit breaker/retry/caching code — infra layer only.
- **Migration equivalent**: first-ever infra creation (net-new `CREATE`,
  nothing destructive) — no expand/contract concern. Per-service database
  creation via the `_db-provision-job` Helm hook is additive by design
  (creates a new database/role per service, never touches another
  service's database) and is idempotent (safe to re-run on every
  `helm upgrade`).
- **Backup/DR**: the shared RDS instance follows
  `docs/backup-and-disaster-recovery.md`'s existing table as-is (automated
  snapshots + PITR; dev has no cross-region requirement, RPO "None
  (ephemeral)"). No edit to that doc required.
- **Cost impact** (first infra ever created — essentially all new spend):

| Resource | Rough monthly cost (dev, running 24/7 — mitigated by scale-to-zero, item 10) |
|---|---|
| EKS control plane | ~$73 (fixed, cannot scale to zero) |
| 1x on-demand node (t4g.medium baseline) | ~$24 |
| Spot burst nodes | ~$0 idle, variable when bursting |
| 1x NAT Gateway (single, dev-only cost decision) | ~$33 + data processing |
| RDS db.t4g.micro, single-AZ, 20GB gp3 | ~$15 |
| ElastiCache cache.t4g.micro, single node | ~$11 |
| Secrets Manager (3 secrets) | ~$1.20 |
| S3 + DynamoDB (bootstrap) | <$1 |
| **Estimated total if continuous** | **~$155-160/mo** |

  Scale-to-zero (item 10, now in scope) substantially reduces the
  effective monthly cost by stopping compute/RDS outside working hours —
  EKS control plane's ~$73 remains the one fixed cost that cannot scale to
  zero.
  - Single NAT gateway instead of one-per-AZ deliberately trades HA for
    dev cost (~$33/mo saved per additional AZ) — acceptable for `dev`'s
    "no HA requirement" posture.

## 8. Test plan reference

No `.tf` files exist yet, so there is no `terraform plan` diff at this
stage. Once written, per `.claude/skills/terraform-conventions/SKILL.md`:
1. `terraform fmt -check` and `terraform validate` clean on every module and `environments/dev`.
2. `tflint` and `checkov`/`tfsec` clean, or every finding explicitly justified.
3. `terraform plan` run against `environments/dev` (and separately `bootstrap/`), full output for human review.
4. Helm: `helm lint` on `_lib` plus a template render (`helm template`) against a synthetic values file, including a rendered check of the `_db-provision-job` hook template.

## 9. Resolved decisions (formerly open questions)

### 9.1 Per-service database provisioning — Kubernetes Job (resolved)

The `postgresql` provider needs network reachability into the VPC's
private subnet, which neither a human's laptop nor a CI runner has by
default. **Resolved: per-service database/role creation happens via a
Kubernetes Job** (the `_db-provision-job` Helm template in `_lib`),
running inside the cluster as a pre-install/pre-upgrade hook on each
service's own Helm release — not via a Terraform `postgresql` provider
resource. This fits naturally alongside each service's own Alembic
migrations (CLAUDE.md §2.5), which already need something to run
inside-cluster before an empty database can be migrated. No bastion host
or SSM tunnel is needed as a result.

### 9.2 Scale-to-zero — included in this plan (resolved)

Folded into scope now (item 10, `modules/scale-to-zero/`) rather than a
fast-follow, to avoid paying the full ~$155-160/mo run rate from day one.

### 9.3 EKS endpoint access — public+private, restricted to operator IP (resolved)

Simpler for solo/dev work than a permanent bastion or VPN. The CIDR
allowlist (`cluster_endpoint_public_access_cidrs`) needs periodic manual
updates as the operator's IP changes — accepted trade-off for `dev`.

### 9.4 Minor defaults adopted (not re-litigated, following `infra-agent`'s recommendation)

- RDS master credential: `manage_master_user_password = true` (RDS-managed, never plaintext in Terraform).
- `CostCenter` tag: `platform-shared` for resources in this plan; future service-specific resources use the service's own name.
- Bootstrap state: local, gitignored, operator keeps a personal backup; documented as a runbook in `bootstrap/README.md`.
- **Known doc/reality gap, not fixed by this plan**: `docs/secrets-management.md`'s inventory table claims the ElastiCache auth-token rotates automatically ("Automatic (ElastiCache rotation)"), but ElastiCache has no Secrets-Manager-native rotation Lambda the way RDS does. Flagged for a future doc correction or a small custom rotation Lambda — not blocking this plan since the auth token isn't yet in active use.

---

## Addendum — 2026-08-24, post-execution reconciliation

`infra-agent` and `identity-agent`'s execution agents ran concurrently and
wrote mutually-inconsistent naming in a few places, caught by validating
the combined `terraform plan`/`helm template` output after both finished.
Fixed directly (mechanical corrections, not new architectural decisions),
plus one approved scope addition and one approved scope completion:

- **Naming reconciliation**: `identity-service.tf`'s references to
  `module.rds`/`module.secrets` outputs corrected to match this plan's
  actual output names; `_lib`'s three named templates
  (`serviceAccount`/`networkPolicy`/`dbProvisionJob`) and identity-service's
  matching `include` calls reconciled to the same casing; the
  `_db-provision-job.tpl` script now emits a `database_url` field (with a
  per-consumer `urlScheme`, not hardcoded) that the ExternalSecret side
  already expected.
- **Scope addition (human-approved)**: `internal-reveal-credential` added
  to `infra/terraform/modules/secrets/` as a new per-service Secrets
  Manager container + IRSA read grant, following the exact pattern of
  `jwt-signing-key`/`db-credentials` — needed for identity-service's
  reference+secret internal reveal endpoint, not originally in this
  plan's scope.
- **Scope completion**: the `db-provision` container image
  (`infra/k8s/images/db-provision/`, referenced but not built when this
  plan was first executed) is now built, smoke-tested (`psql`, `aws` CLI,
  `python3` all confirmed working in the image), and has its own ECR
  repository (`infra/terraform/modules/ecr`, generic — also used for
  identity-service's own app image) and CI workflow
  (`.github/workflows/db-provision-image-ci.yml`).

Final combined `terraform plan` (bootstrap + this plan + identity-service's
Terraform footprint, all in one `environments/dev/` run): **84 to add, 0 to
change, 0 to destroy**, no errors. `terraform apply` still not run by any
agent.

**What still requires human action:**
- Only after `/implementation-execution` writes the actual `.tf`/Helm
  files does a real `terraform plan` output exist for review.
- Even then, only `terraform plan` is run by an agent — the human runs
  the actual `terraform apply` for `bootstrap/` and then
  `environments/dev/`, in that order, per CLAUDE.md §7 and
  `.claude/hooks/pre-terraform-guard.sh`.
