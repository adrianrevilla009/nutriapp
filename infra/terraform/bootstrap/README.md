# Terraform Bootstrap — Remote State Backend

This is a standalone root module, **applied once, manually, by a human**,
outside the normal `environments/<env>/` workflow. It solves the
chicken-and-egg problem of remote state: every environment's backend
needs an S3 bucket + DynamoDB table to exist *before* that environment
can `terraform init` against them.

Per `docs/terraform-and-infrastructure.md` section 6 and CLAUDE.md
section 7, this module's state is kept **local**, not remote, and is
**never applied by an agent** — only `terraform plan` may be run
unattended (enforced by `.claude/hooks/pre-terraform-guard.sh`).

## What it creates

- One versioned, encrypted, fully-private S3 bucket
  (`nutriapp-tfstate-<account-id>-<region>`) that holds every
  environment's `.tfstate` file, one object key per environment.
- One DynamoDB table (`nutriapp-tfstate-lock`) for state locking, shared
  across environments (locking is keyed per state file automatically).

## One-time manual runbook (human only)

```bash
cd infra/terraform/bootstrap
terraform init
terraform plan -out=bootstrap.tfplan
# Review the plan output carefully — this is the only time these
# specific resources are created.
terraform apply bootstrap.tfplan
```

After apply succeeds, record the outputs:

```bash
terraform output
```

You will need `state_bucket_name` and `lock_table_name` to populate each
environment's `backend.hcl` (see
`infra/terraform/environments/dev/backend.hcl.example`).

## State handling — read before touching this directory

- This module's own `terraform.tfstate` stays **local** (gitignored, see
  `infra/terraform/.gitignore`) — it cannot bootstrap its own remote
  backend.
- **Keep a personal backup of `terraform.tfstate` and
  `terraform.tfstate.backup`** (e.g. copy to an encrypted volume or a
  password manager's file attachment) outside this repo. If this file is
  lost, the S3 bucket and DynamoDB table still exist in AWS but Terraform
  no longer tracks them — they become recoverable only via
  `terraform import` (tedious but possible), not resource loss.
- Do not attempt to migrate this module to an S3 backend pointing at the
  very bucket it creates — that's a real but unnecessary complication at
  this project's scale; local state for this one bootstrap module is the
  accepted trade-off (see the implementation plan, section 9.4).

## Re-running this module

Safe to re-run `terraform plan`/`apply` if you need to change tags or
add a lifecycle rule later — every resource here is additive-safe. Never
run `terraform destroy` against this module while any environment still
has state stored in the bucket it manages.

## Guardrail reminder

An agent may run `terraform init`, `terraform fmt`, `terraform validate`,
`tflint`, `checkov`/`tfsec`, and `terraform plan` in this directory
freely. An agent must **never** run `terraform apply` or
`terraform destroy` here, with or without `-auto-approve` — that is
exclusively a human action.
