# infra/terraform/modules/scale-to-zero/outputs.tf

output "lambda_function_arn" {
  value = aws_lambda_function.this.arn
}

output "lambda_function_name" {
  value = aws_lambda_function.this.function_name
}

output "scale_down_schedule_arn" {
  value = aws_scheduler_schedule.scale_down.arn
}

output "scale_up_schedule_arn" {
  value = aws_scheduler_schedule.scale_up.arn
}
