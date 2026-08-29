# infra/terraform/environments/dev/terraform.tfvars
#
# Dev sizing only — no secret values (per CLAUDE.md section 7 and
# .claude/skills/terraform-conventions/SKILL.md). Every value here is
# safe to commit.
#
# EXCEPTION: cluster_endpoint_public_access_cidrs below is left at its
# variables.tf placeholder (RFC 5737 TEST-NET-3, never routable). The
# operator must override it — via a gitignored terraform.tvars.local, not
# by editing this file — with their real current public IP before a real
# apply. See variables.tf's description for why.

aws_region  = "us-east-1"
environment = "dev"

vpc_cidr             = "10.20.0.0/16"
availability_zones   = ["us-east-1a", "us-east-1b", "us-east-1c"]
public_subnet_cidrs  = ["10.20.0.0/24", "10.20.1.0/24", "10.20.2.0/24"]
private_subnet_cidrs = ["10.20.10.0/24", "10.20.11.0/24", "10.20.12.0/24"]

cluster_name       = "nutriapp-dev"
kubernetes_version = "1.32"
namespace          = "nutriapp-dev"

rds_instance_class    = "db.t4g.micro"
rds_allocated_storage = 20
rds_multi_az          = false

redis_node_type = "cache.t4g.micro"

jwt_signing_key_service_names = ["identity-service"]
# NOTE: catalog-service, nutrition-calculation-service, and
# food-recognition-service are each already missing from this override
# list despite needing a db-credentials container -- a pre-existing gap
# from those services' own worktrees (variables.tf's default already
# lists all five; this override silently narrows it), not introduced or
# fixed here. "notification-service" and "billing-service" are added
# below because each needs its own db-credentials container (this
# session's billing-service implementation plan); the other three remain
# a separately tracked follow-up, not silently expanded to fix here.
db_credential_service_names = ["identity-service", "profile-service", "diary-service", "notification-service", "billing-service"]

# billing-service's own internal, non-Kong-routed entitlement-check
# endpoint (GET /internal/v1/billing/entitlements/{user_id}, implementation
# plan section 1.4) -- zero real callers today, same deferral pattern as
# the endpoint itself.
internal_reveal_credential_service_names = ["identity-service", "billing-service"]

scale_down_schedule_expression = "cron(0 20 ? * MON-FRI *)"
scale_up_schedule_expression   = "cron(0 7 ? * MON-FRI *)"
schedule_timezone              = "UTC"
