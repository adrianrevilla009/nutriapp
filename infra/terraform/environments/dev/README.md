# environments/dev

Thin composition of `infra/terraform/modules/*` for the `dev`
environment. See `infra/terraform/README.md` for the module dependency
order and `docs/terraform-and-infrastructure.md` section 2 for `dev`'s
sizing/auto-shutdown posture.

## First-time setup (after `bootstrap/` has been applied by a human)

```bash
cd infra/terraform/environments/dev
cp backend.hcl.example backend.hcl   # fill in from `terraform output` in bootstrap/
terraform init -backend-config=backend.hcl
```

Before any real `apply`, override `cluster_endpoint_public_access_cidrs`
with your actual current public IP — do this via a gitignored
`terraform.tfvars.local` (not by editing the committed
`terraform.tfvars`, which intentionally ships a non-routable RFC 5737
placeholder):

```bash
echo 'cluster_endpoint_public_access_cidrs = ["<your-ip>/32"]' > terraform.tfvars.local
```

Terraform automatically loads `*.auto.tfvars`/`terraform.tfvars.local`
is NOT auto-loaded by Terraform itself — pass it explicitly:

```bash
terraform plan -var-file=terraform.tfvars.local
```

## What an agent may/may not do here

- May run freely: `terraform fmt`, `terraform validate`, `tflint`,
  `checkov`/`tfsec`, `terraform plan`.
- Must never run: `terraform apply`, `terraform destroy` — human-only,
  per CLAUDE.md section 7 and `.claude/hooks/pre-terraform-guard.sh`.

## Identity-service coordination

`identity-service`'s own implementation plan adds
`infra/terraform/environments/dev/identity-service.tf` to this same
directory, referencing this file's module outputs
(`module.rds.*`, `module.secrets.*`, `module.eks.*` — see `outputs.tf`
for the full list) rather than recreating any platform-layer resource.
That file is out of this plan's scope and is not touched here.

## Notable resource notes

- **First-ever `terraform plan` on an empty account**: the `kubernetes`
  provider (`providers.tf`) is configured from `module.eks`'s outputs,
  which don't exist yet before the first apply. This is expected and
  normal — Terraform defers the provider's connection until the EKS
  cluster resource is actually created during `apply`; `plan` shows the
  namespace/NetworkPolicy resources as "known after apply" rather than a
  concrete diff. No special `-target` sequencing is required for a
  routine `apply`.
- **`cluster_endpoint_public_access_cidrs`** needs periodic manual
  updates as the operator's IP changes (implementation plan section
  9.3) — there is no automation for this by design at this scale.
