# infra/terraform/modules/elasticache/outputs.tf

output "primary_endpoint_address" {
  value = aws_elasticache_replication_group.this.primary_endpoint_address
}

output "port" {
  value = aws_elasticache_replication_group.this.port
}

output "security_group_id" {
  value = aws_security_group.this.id
}

output "auth_token_secret_arn" {
  description = "Secrets Manager ARN holding {\"auth_token\": ...} for this Redis replication group."
  value       = aws_secretsmanager_secret.auth_token.arn
}
