# infra/terraform/modules/rds/outputs.tf

output "db_instance_id" {
  value = aws_db_instance.this.id
}

output "db_instance_arn" {
  value = aws_db_instance.this.arn
}

output "db_instance_address" {
  value = aws_db_instance.this.address
}

output "db_instance_endpoint" {
  description = "host:port"
  value       = aws_db_instance.this.endpoint
}

output "db_instance_port" {
  value = aws_db_instance.this.port
}

output "master_username" {
  value = aws_db_instance.this.username
}

output "master_user_secret_arn" {
  description = "Secrets Manager ARN of the RDS-managed master credential (manage_master_user_password=true)."
  value       = aws_db_instance.this.master_user_secret[0].secret_arn
}

output "security_group_id" {
  value = aws_security_group.this.id
}

output "db_subnet_group_name" {
  value = aws_db_subnet_group.this.name
}
