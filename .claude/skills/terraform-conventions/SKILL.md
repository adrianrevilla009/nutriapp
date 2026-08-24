---
description: Terraform module and workflow conventions for NutriApp's AWS infrastructure. Use whenever creating or modifying any file under infra/terraform/.
---

# Terraform Conventions — NutriApp

Full policy: `docs/terraform-and-infrastructure.md`.

## Structure Rule
- Reusable logic lives in `infra/terraform/modules/<name>/`, environment-agnostic
  (no hardcoded env names, account IDs, or CIDR ranges inside a module).
- `infra/terraform/environments/<env>/` only calls modules and supplies variables.
- Never write resources directly in an `environments/<env>/main.tf` unless it
  is truly environment-unique (e.g. the DNS zone).

## Non-Negotiables
- `terraform fmt` and `terraform validate` clean before any commit.
- Every resource tagged: `Project`, `Environment`, `Service`, `ManagedBy = terraform`.
- Remote state only (S3 + DynamoDB lock) — never local state.
- **`terraform apply` and `terraform destroy` are never run by an agent.**
  Only `terraform plan`. Present the plan output to the human and wait for
  explicit confirmation before they (or an approved manual workflow) apply
  it. This is enforced by `.claude/hooks/pre-terraform-guard.sh` — do not
  attempt to route around it via a raw `aws` CLI call instead.
- No secret values written into `.tf`/`.tfvars` files — reference Secrets
  Manager via a data source, or pass through a CI secret store.

## Before Proposing Any Terraform Change
1. Run `terraform fmt` and `terraform validate`.
2. Run `tflint` and `checkov`/`tfsec` — fix or explicitly justify any finding.
3. Run `terraform plan` and include the output in the implementation plan for
   human review (CLAUDE.md section 6).
