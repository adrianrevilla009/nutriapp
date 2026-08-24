# infra/terraform

Full policy: `docs/terraform-and-infrastructure.md`. Conventions:
`.claude/skills/terraform-conventions/SKILL.md`.

## Layout

```
infra/terraform/
  bootstrap/        # one-time, human-applied, local state — see bootstrap/README.md
  modules/           # reusable, environment-agnostic
    vpc/
    eks/
    rds/
    elasticache/
    secrets/
    scale-to-zero/
  environments/
    dev/             # thin composition of the modules above, dev-sized
    staging/         # not yet created
    prod/             # not yet created
```

## Module dependency order

`environments/dev/main.tf` wires modules in this order (each depends on
outputs from the one(s) before it):

1. `vpc` — no dependencies.
2. `eks` — depends on `vpc` (subnet IDs).
3. `rds` / `elasticache` — depend on `vpc` (subnets) and `eks` (cluster
   security group, as the allowed ingress source).
4. `secrets` — depends on `eks` (OIDC provider, for IRSA trust policies)
   and `rds` (master credential secret ARN, for the db-provision-job's
   read access).
5. `scale-to-zero` — depends on `eks` (node group names) and `rds`
   (instance ID/ARN).
6. The namespace + default-deny NetworkPolicy (`namespace.tf`) — depend
   on `eks` (cluster endpoint, for the `kubernetes` provider).

`staging`/`prod` (when created) reuse the same modules unchanged, per
`.claude/skills/terraform-conventions/SKILL.md`'s Structure Rule — only
`environments/<env>/terraform.tfvars` differs.

## Workflow

An agent may run `terraform fmt`, `terraform validate`, `tflint`,
`checkov`/`tfsec`, and `terraform plan` freely, in `bootstrap/` and every
`environments/<env>/`. **An agent never runs `terraform apply` or
`terraform destroy`**, in any environment, under any flag — enforced by
`.claude/hooks/pre-terraform-guard.sh` and CLAUDE.md section 7. Present
`terraform plan` output for explicit human review; the human runs
`apply` themselves (or approves a manually-triggered CI workflow run).

Apply order for a from-scratch account: `bootstrap/` first (once,
manually), then `environments/dev/`.
