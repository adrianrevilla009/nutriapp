# infra/terraform/bootstrap/outputs.tf

output "state_bucket_name" {
  description = "S3 bucket name to reference in every environments/<env>/backend.hcl."
  value       = aws_s3_bucket.state.bucket
}

output "state_bucket_arn" {
  value = aws_s3_bucket.state.arn
}

output "lock_table_name" {
  description = "DynamoDB table name to reference in every environments/<env>/backend.hcl."
  value       = aws_dynamodb_table.lock.name
}

output "lock_table_arn" {
  value = aws_dynamodb_table.lock.arn
}

output "aws_region" {
  value = var.aws_region
}
