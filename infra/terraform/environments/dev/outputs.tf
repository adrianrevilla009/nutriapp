# infra/terraform/environments/dev/outputs.tf
#
# Predictable, named outputs any later file added to this same directory
# (e.g. identity-service's own identity-service.tf, owned by a separate
# plan) references directly as module.<name>.<output> — these `output`
# blocks additionally make the values visible via `terraform output` for
# human review.

output "vpc_id" {
  value = module.vpc.vpc_id
}

output "private_subnet_ids" {
  value = module.vpc.private_subnet_ids
}

output "public_subnet_ids" {
  value = module.vpc.public_subnet_ids
}

output "eks_cluster_name" {
  value = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "eks_oidc_provider_arn" {
  value = module.eks.oidc_provider_arn
}

output "eks_oidc_provider_url" {
  value = module.eks.oidc_provider_url
}

output "eks_cluster_primary_security_group_id" {
  value = module.eks.cluster_primary_security_group_id
}

output "rds_endpoint" {
  value = module.rds.db_instance_endpoint
}

output "rds_port" {
  value = module.rds.db_instance_port
}

output "rds_master_user_secret_arn" {
  value = module.rds.master_user_secret_arn
}

output "rds_security_group_id" {
  value = module.rds.security_group_id
}

output "redis_endpoint" {
  value = module.elasticache.primary_endpoint_address
}

output "redis_port" {
  value = module.elasticache.port
}

output "redis_auth_secret_arn" {
  value = module.elasticache.auth_token_secret_arn
}

output "namespace" {
  value = kubernetes_namespace.app.metadata[0].name
}

output "jwt_signing_key_secret_arns" {
  value = module.secrets.jwt_signing_key_secret_arns
}

output "db_credential_secret_arns" {
  value = module.secrets.db_credential_secret_arns
}

output "db_provision_irsa_role_arns" {
  value = module.secrets.db_provision_irsa_role_arns
}

output "app_secrets_irsa_role_arns" {
  value = module.secrets.app_secrets_irsa_role_arns
}

output "internal_reveal_credential_secret_arns" {
  value = module.secrets.internal_reveal_credential_secret_arns
}

# profile-service implementation plan Addendum 2: the reveal-metrics
# endpoint's distinct, per-caller credential and its dedicated caller IRSA
# role. This second output in particular is the reconciliation point for
# nutrition-calculation-service's own (separately developed) Terraform --
# that service's chart/ServiceAccount wires this role's ARN in as its
# IRSA annotation, or, at /implementation-review, this single statement is
# merged into whatever role that service's app pod already assumes.
output "cross_service_reveal_credential_secret_arns" {
  value = module.secrets.cross_service_reveal_credential_secret_arns
}

output "cross_service_reveal_credential_caller_irsa_role_arns" {
  value = module.secrets.cross_service_reveal_credential_caller_irsa_role_arns
}

output "scale_to_zero_lambda_arn" {
  value = module.scale_to_zero.lambda_function_arn
}

output "db_provision_ecr_repository_url" {
  value = module.ecr_db_provision.repository_url
}
