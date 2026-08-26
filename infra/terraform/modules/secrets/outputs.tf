# infra/terraform/modules/secrets/outputs.tf

output "jwt_signing_key_secret_arns" {
  description = "Map of service name -> Secrets Manager ARN holding {algorithm, private_key_pem, public_key_pem}."
  value       = { for k, v in aws_secretsmanager_secret.jwt_signing_key : k => v.arn }
}

output "db_credential_secret_arns" {
  description = "Map of service name -> Secrets Manager ARN holding {username, password} once populated by that service's _db-provision-job hook."
  value       = { for k, v in aws_secretsmanager_secret.db_credentials : k => v.arn }
}

output "db_provision_irsa_role_arns" {
  description = "Map of service name -> IAM role ARN for that service's _db-provision-job ServiceAccount (\"<service>-db-provision\")."
  value       = { for k, v in aws_iam_role.db_provision : k => v.arn }
}

output "app_secrets_irsa_role_arns" {
  description = "Map of service name -> IAM role ARN for that service's app ServiceAccount (\"<service>\"), scoped to read only that service's own secrets."
  value       = { for k, v in aws_iam_role.app_secrets : k => v.arn }
}

output "internal_reveal_credential_secret_arns" {
  description = "Map of service name -> Secrets Manager ARN holding {credential}, the shared bearer credential for that service's internal, non-Kong-routed endpoints (e.g. identity-service's token-reveal endpoint, verified against a caller-presented value)."
  value       = { for k, v in aws_secretsmanager_secret.internal_reveal_credential : k => v.arn }
}

output "usda_fdc_api_key_secret_arns" {
  description = "Map of service name -> Secrets Manager ARN holding {api_key}, a third-party USDA FoodData Central API key populated manually, out-of-band (e.g. catalog-service's USDA FDC ingestion adapter)."
  value       = { for k, v in aws_secretsmanager_secret.usda_fdc_api_key : k => v.arn }
}
