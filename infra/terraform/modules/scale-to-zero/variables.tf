# infra/terraform/modules/scale-to-zero/variables.tf
#
# Dev-only cost control (docs/cost-management.md section 1): scales EKS
# node groups to 0 and stops the RDS instance outside working hours,
# restoring both on a schedule.

variable "name_prefix" {
  type    = string
  default = "nutriapp-dev-scale-to-zero"
}

variable "cluster_name" {
  type = string
}

variable "rds_instance_id" {
  type = string
}

variable "rds_instance_arn" {
  description = "Used to scope the Lambda's IAM policy to exactly this instance."
  type        = string
}

variable "node_group_baselines" {
  description = "Map of node-group name -> baseline {desired, min, max} to restore on scale-up."
  type = map(object({
    desired = number
    min     = number
    max     = number
  }))
}

variable "scale_down_schedule_expression" {
  description = "EventBridge Scheduler cron expression, evaluated in var.schedule_timezone. Default: weekdays 20:00 (end of working hours)."
  type        = string
  default     = "cron(0 20 ? * MON-FRI *)"
}

variable "scale_up_schedule_expression" {
  description = "EventBridge Scheduler cron expression. Default: weekdays 07:00 (start of working hours). Weekends stay scaled down entirely — no scale-up rule fires Sat/Sun."
  type        = string
  default     = "cron(0 7 ? * MON-FRI *)"
}

variable "schedule_timezone" {
  type    = string
  default = "UTC"
}

variable "lambda_timeout_seconds" {
  type    = number
  default = 60
}

variable "tags" {
  type    = map(string)
  default = {}
}
