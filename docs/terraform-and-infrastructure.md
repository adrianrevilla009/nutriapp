# Terraform & AWS Infrastructure

Full specification behind CLAUDE.md's infra summary. See ADR-0006 (EKS) and
ADR-0007 (secrets) for the underlying platform decisions this infra provisions.

## 1. Structure

```
infra/terraform/
  environments/
    dev/       # thin: backend config + module calls + env-specific variables
    staging/
    prod/
  modules/
    vpc/               # VPC, subnets (public/private), NAT gateways, routing
    eks/                # EKS cluster, node groups (on-demand + spot), IRSA setup
    rds/                # Postgres instances, one per service-group, param groups
    elasticache/         # Redis cluster
    messaging/            # RabbitMQ (self-hosted on EKS via Helm) or MSK, per ADR-0004
    qdrant/               # Qdrant deployment (self-hosted on EKS or Cloud, per environment)
    secrets/              # Secrets Manager secrets + IAM policies for IRSA
    observability/         # Managed Prometheus/Grafana (AMP/AMG) or self-hosted resources
    dns-and-tls/            # Route53 zones, ACM certificates
  README.md
```

- **Modules are reusable and environment-agnostic**; `environments/<env>/`
  files only supply variables (instance sizes, replica counts, CIDR ranges).
- **Remote state**: S3 backend (versioned, encrypted bucket) + DynamoDB table
  for state locking, one state file per environment (never shared).
- **No hardcoded account IDs or ARNs** in module code — passed as variables,
  sourced from environment-specific `.tfvars` (non-secret) or Secrets Manager
  (secret values, referenced via `data "aws_secretsmanager_secret_version"`,
  never written to state as plaintext where avoidable).

## 2. Environments

| Environment | Purpose                                | Sizing                          | Auto-shutdown |
|--------------|-----------------------------------------|------------------------------------|-----------------|
| `dev`         | Integration testing, agent-driven development | Smallest viable (t-class nodes, single-AZ RDS) | Yes — scaled to zero outside working hours via a scheduled Lambda, see `docs/cost-management.md` |
| `staging`      | Pre-prod validation, E2E and load testing        | Mirrors prod topology at smaller scale | No |
| `prod`         | Production traffic                                 | Multi-AZ, autoscaling, RDS with read replicas | No |

## 3. Core Resources per Environment

- **VPC**: 3 AZs, public subnets (ALB, NAT gateways only) and private subnets
  (EKS nodes, RDS, ElastiCache, RabbitMQ, Qdrant) — no database or internal
  service is ever in a public subnet.
- **EKS**: managed node groups split between on-demand (baseline capacity)
  and spot (burst capacity for non-critical, interruption-tolerant workloads
  like async event projectors); cluster autoscaler enabled.
- **RDS**: PostgreSQL, one instance per service-group sharing infra where the
  data volume doesn't justify full isolation yet (documented per-service in
  each service's README), Multi-AZ in `prod`, automated backups (see
  `docs/backup-and-disaster-recovery.md`).
- **ElastiCache (Redis)**: cluster mode for `prod`, single node for `dev`.
- **Messaging**: RabbitMQ self-hosted on EKS via the Bitnami Helm chart with
  persistent volumes in `dev`/`staging`; re-evaluate Amazon MQ (managed
  RabbitMQ) for `prod` once operational load is measured (documented as an
  open question in ADR-0004, not yet resolved).
- **Qdrant**: self-hosted on EKS with persistent volumes for `dev`/`staging`;
  Qdrant Cloud considered for `prod` if self-hosting the vector store proves
  operationally heavy — tracked as a follow-up ADR trigger.

## 4. Human-in-the-Loop Guardrail for Terraform

Mirroring CLAUDE.md section 7: **`terraform apply` and `terraform destroy`
are never run by an agent without explicit human confirmation**, in any
environment, enforced by `.claude/hooks/pre-terraform-guard.sh`. Agents may
run `terraform plan` freely (read-only against state, side-effect-free
against real infra) and must present the plan output for human review before
any apply.

## 5. Tagging Convention

Every resource is tagged with:
- `Project = nutriapp`
- `Environment = dev|staging|prod`
- `Service = <service-name>` (or `shared` for cross-cutting infra)
- `ManagedBy = terraform`
- `CostCenter` (for future cost allocation reporting)

## 6. State & Access

- State bucket and lock table are themselves provisioned by a small
  bootstrap Terraform config (`infra/terraform/bootstrap/`), applied once
  manually, outside the normal environment workflow (chicken-and-egg problem
  for remote state).
- IAM: a dedicated `terraform-deployer` role per environment, assumed via
  OIDC from GitHub Actions for `plan` only; `apply` is run from a human's
  authenticated AWS CLI session (or a manually-triggered, human-approved
  workflow run), never from an unattended CI job.

## 7. Module Versioning

- Modules pin provider versions explicitly (`required_providers` block).
- Breaking changes to a shared module bump its internal version comment and
  require re-running `terraform plan` against every environment that
  consumes it before merge.
