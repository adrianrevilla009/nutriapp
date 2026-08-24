# Secrets Management

Full specification behind CLAUDE.md and `docs/security-and-compliance.md`
section 2. See ADR-0007 for the platform decision (AWS Secrets Manager +
External Secrets Operator).

## 1. Secret Inventory (per service, minimum)

| Secret                              | Owner service        | Rotation                     |
|--------------------------------------|------------------------|---------------------------------|
| Database credentials                  | each service            | Automatic (Secrets Manager RDS rotation, 30 days) |
| JWT signing key pair                  | `identity-service`       | Manual, every 90 days, documented runbook |
| RabbitMQ credentials                   | shared (per-service vhost/user) | Automatic where supported, else manual/90 days |
| Vision API key                         | `food-recognition-service`          | Manual, per provider's rotation support |
| LLM provider API key                    | `nutrition-assistant-service`          | Manual, per provider's rotation support |
| Qdrant API key                           | `nutrition-assistant-service`          | Manual, 90 days |
| Redis auth token                          | shared                      | Automatic (ElastiCache rotation) |

## 2. Flow

1. Secret is created/updated in **AWS Secrets Manager** (never manually in
   the cluster).
2. **External Secrets Operator** (ESO), running in-cluster with an IRSA role
   scoped to read only the secrets its namespace needs, syncs it into a
   native Kubernetes `Secret` object on a poll interval (default 1h, or
   triggered on webhook for urgent rotations).
3. Pods reference the Kubernetes `Secret` via environment variables or a
   mounted volume — application code never calls AWS APIs directly to fetch a
   secret (keeps infra concerns out of the domain/application layers, per the
   hexagonal architecture rule in CLAUDE.md 2.1).
4. On rotation, ESO updates the Kubernetes `Secret`; pods that need to pick up
   the new value are restarted via a rollout (automated for RDS-rotated
   secrets using the `reloader` controller watching the `Secret`'s hash).

## 3. Local Development

- Each service has a `.env.example` with placeholder values, committed to
  git.
- Developers (human or agent-assisted) copy it to `.env` (git-ignored) and
  fill in local values (pointed at the `docker-compose` stack, never at real
  AWS resources).
- `docker-compose.yml` reads each service's `.env` via `env_file`.

## 4. Access Control

- IRSA (IAM Roles for Service Accounts): each service's Kubernetes
  `ServiceAccount` is annotated with an IAM role that can read **only** the
  Secrets Manager secrets that service owns — enforced by a scoped IAM policy,
  not convention.
- No shared "god" IAM role that can read every secret in the account.
- Human access to Secrets Manager in `prod` requires MFA and is logged via
  CloudTrail; `security-agent` reviews access policy changes as part of any
  infra PR touching `infra/terraform/modules/secrets/`.

## 5. What Must Never Happen

- A secret value committed to git, even in a "temporary" branch or a
  since-reverted commit (git history retains it — if it happens, the secret
  is rotated immediately, not just removed from the file).
- A secret logged, even at debug level, even partially (e.g. logging "token
  starts with...").
- A secret baked into a container image layer.
- A secret passed as a `docker build --build-arg` (visible in image history).
- An agent running any command that could exfiltrate a secret value (e.g.
  `echo $DATABASE_PASSWORD` in a shared log) — `security-agent` flags this on
  review, and `pre-bash-guard.sh` blocks direct reads of files under
  `.claude/` or `.env` from being echoed to stdout in agent-run commands.

## 6. Manual Rotation Runbook (for secrets without native rotation)

1. Generate the new secret value (never reuse or derive from the old one).
2. Create a new version in Secrets Manager (do not delete the old version
   yet — Secrets Manager supports staged rotation with `AWSPENDING`/
   `AWSCURRENT` labels).
3. Confirm ESO has synced the new value into the cluster.
4. Roll the affected deployments.
5. Verify the service is healthy against the new credential.
6. Only then, deprecate/delete the old secret version.
7. Record the rotation date in `docs/secrets-management.md`'s inventory table
   (update the "last rotated" note — add a column if the table grows) so the
   next rotation due-date is trackable.
