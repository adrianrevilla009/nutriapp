# db-provision image

Shared utility image consumed by every NutriApp service's
`_db-provision-job.tpl` Helm hook
(`infra/k8s/charts/_lib/templates/_db-provision-job.tpl`, platform-infra
plan §9.1). Not a NutriApp "service" — one image, reused unchanged by
every future service's own `<service>.tf` Terraform wiring
(`dbProvision.image.repository` in that service's `helm_release` values).

## What it does

Provides `psql`, the `aws` CLI, and `python3` on `PATH` for the Job's
embedded `provision.sh` script, which:
1. Reads the shared RDS instance's master credentials from Secrets Manager.
2. Creates the calling service's own logical database + role, if they
   don't already exist (idempotent — safe on every `helm upgrade`).
3. Writes the newly generated per-service credentials (including a
   composed `database_url` connection string) back to that service's own
   `db-credentials` Secrets Manager entry.

## Build / CI

Built and scanned by `.github/workflows/db-provision-image-ci.yml` on any
change under this directory. Pushed to the `nutriapp/db-provision` ECR
repository (`infra/terraform/modules/ecr`, instantiated in
`infra/terraform/environments/dev/main.tf` as `module.ecr_db_provision`)
— push/deploy wiring is a follow-up once that Terraform is actually
applied and an EKS cluster exists, same sequencing as every service's own
image (see `services/identity-service/README.md`).

Local build/smoke-test:
```
docker build -t nutriapp/db-provision:local .
docker run --rm nutriapp/db-provision:local sh -c 'psql --version && aws --version && python3 --version'
```
