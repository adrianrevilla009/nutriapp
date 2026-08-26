# infra/terraform/environments/dev/main.tf
#
# Thin composition of environment-agnostic modules, dev-sized. Per
# .claude/skills/terraform-conventions/SKILL.md, no resources are written
# directly here except what is truly environment-unique (the namespace/
# NetworkPolicy baseline in namespace.tf).
#
# identity-service's own plan (`/plans/identity-service/implementation-plan.md`)
# adds its own file (identity-service.tf) to this same directory later,
# referencing the module outputs below (module.rds.*, module.secrets.*,
# etc.) rather than recreating any platform-layer resource.

module "vpc" {
  source = "../../modules/vpc"

  name                 = var.cluster_name
  vpc_cidr             = var.vpc_cidr
  availability_zones   = var.availability_zones
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  single_nat_gateway   = true # dev cost decision — see docs/terraform-and-infrastructure.md section 3
  cluster_name         = var.cluster_name

  tags = local.common_tags
}

module "eks" {
  source = "../../modules/eks"

  cluster_name                         = var.cluster_name
  kubernetes_version                   = var.kubernetes_version
  vpc_id                               = module.vpc.vpc_id
  private_subnet_ids                   = module.vpc.private_subnet_ids
  public_subnet_ids                    = module.vpc.public_subnet_ids
  cluster_endpoint_public_access_cidrs = var.cluster_endpoint_public_access_cidrs

  # dev sizing: small on-demand baseline, spot for burst, both scaled to
  # zero outside working hours by module.scale_to_zero.
  on_demand_desired_size = 1
  on_demand_min_size     = 0
  on_demand_max_size     = 3
  spot_desired_size      = 0
  spot_min_size          = 0
  spot_max_size          = 5

  tags = local.common_tags
}

module "rds" {
  source = "../../modules/rds"

  identifier                 = "${var.cluster_name}-postgres"
  vpc_id                     = module.vpc.vpc_id
  private_subnet_ids         = module.vpc.private_subnet_ids
  allowed_security_group_ids = [module.eks.cluster_primary_security_group_id]

  instance_class      = var.rds_instance_class
  allocated_storage   = var.rds_allocated_storage
  multi_az            = var.rds_multi_az
  deletion_protection = false # dev only
  skip_final_snapshot = true  # dev only

  tags = local.common_tags
}

module "elasticache" {
  source = "../../modules/elasticache"

  name                       = "${var.cluster_name}-redis"
  vpc_id                     = module.vpc.vpc_id
  private_subnet_ids         = module.vpc.private_subnet_ids
  allowed_security_group_ids = [module.eks.cluster_primary_security_group_id]
  node_type                  = var.redis_node_type

  tags = local.common_tags
}

module "secrets" {
  source = "../../modules/secrets"

  namespace                  = var.namespace
  environment                = var.environment
  oidc_provider_arn          = module.eks.oidc_provider_arn
  oidc_provider_url          = module.eks.oidc_provider_url
  rds_master_user_secret_arn = module.rds.master_user_secret_arn

  jwt_signing_key_service_names            = var.jwt_signing_key_service_names
  db_credential_service_names              = var.db_credential_service_names
  internal_reveal_credential_service_names = var.internal_reveal_credential_service_names
  usda_fdc_api_key_service_names           = var.usda_fdc_api_key_service_names

  tags = local.common_tags
}

module "ecr_db_provision" {
  source = "../../modules/ecr"

  # Shared platform utility image (infra/k8s/images/db-provision/),
  # consumed by every service's `_db-provision-job.tpl` Helm hook
  # (platform-infra plan §9.1) — one repository, reused unchanged by
  # every future service's identity-service.tf-style wiring, not
  # per-service like modules/secrets' per-service maps.
  repository_name = "nutriapp/db-provision"

  tags = local.common_tags
}

module "scale_to_zero" {
  source = "../../modules/scale-to-zero"

  name_prefix      = "${var.cluster_name}-scale-to-zero"
  cluster_name     = module.eks.cluster_name
  rds_instance_id  = module.rds.db_instance_id
  rds_instance_arn = module.rds.db_instance_arn

  node_group_baselines = {
    "${var.cluster_name}-on-demand" = { desired = 1, min = 0, max = 3 }
    "${var.cluster_name}-spot"      = { desired = 0, min = 0, max = 5 }
  }

  scale_down_schedule_expression = var.scale_down_schedule_expression
  scale_up_schedule_expression   = var.scale_up_schedule_expression
  schedule_timezone              = var.schedule_timezone

  tags = local.common_tags
}

locals {
  common_tags = {
    # Project/Environment/ManagedBy/CostCenter already come from the
    # provider's default_tags (providers.tf) — modules additionally set
    # Service=shared per resource. Nothing extra needed here today; kept
    # as an explicit merge point for any future per-module tag override.
  }
}
