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

output "cross_service_reveal_credential_secret_arns" {
  description = "Map of \"<owner_service>-<caller_service>\" -> Secrets Manager ARN holding {credential}, a per-caller bearer credential for owner_service's internal, non-Kong-routed endpoint (e.g. \"profile-service-nutrition-calculation-service\" for the reveal-metrics endpoint). Read by owner_service's own app_secrets role (already granted below) and by the dedicated caller IRSA role in cross_service_reveal_credential_caller_irsa_role_arns."
  value       = { for k, v in aws_secretsmanager_secret.cross_service_reveal_credential : k => v.arn }
}

output "cross_service_reveal_credential_caller_irsa_role_arns" {
  description = "Map of \"<owner_service>-<caller_service>\" -> IAM role ARN, trusting ONLY caller_service's ServiceAccount, scoped to GetSecretValue on exactly that one cross_service_reveal_credential secret ARN -- nothing else. The caller service's own Helm chart/Terraform wires this ARN into its ServiceAccount's IRSA annotation (or, at /implementation-review reconciliation, this single statement is merged into whatever role that service's app pod already assumes -- a ServiceAccount only ever needs one IRSA role annotation)."
  value       = { for k, v in aws_iam_role.cross_service_reveal_credential_caller : k => v.arn }
}

output "usda_fdc_api_key_secret_arns" {
  description = "Map of service name -> Secrets Manager ARN holding {api_key}, a third-party USDA FoodData Central API key populated manually, out-of-band (e.g. catalog-service's USDA FDC ingestion adapter)."
  value       = { for k, v in aws_secretsmanager_secret.usda_fdc_api_key : k => v.arn }
}

output "anthropic_api_key_secret_arns" {
  description = "Map of service name -> Secrets Manager ARN holding {api_key}, a metered third-party Anthropic API key populated manually, out-of-band (e.g. food-recognition-service's ClaudeVisionAdapter)."
  value       = { for k, v in aws_secretsmanager_secret.anthropic_api_key : k => v.arn }
}

output "stripe_api_key_secret_arns" {
  description = "Map of service name -> Secrets Manager ARN holding {secret_key}, a Stripe secret API key populated manually, out-of-band (billing-service's StripePaymentAdapter)."
  value       = { for k, v in aws_secretsmanager_secret.stripe_api_key : k => v.arn }
}

output "stripe_webhook_signing_secret_secret_arns" {
  description = "Map of service name -> Secrets Manager ARN holding {signing_secret}, a Stripe webhook signing secret (whsec_...) populated manually, out-of-band (billing-service's StripePaymentAdapter.verify_webhook_signature)."
  value       = { for k, v in aws_secretsmanager_secret.stripe_webhook_signing_secret : k => v.arn }
}
