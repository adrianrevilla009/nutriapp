# infra/terraform/modules/eks/outputs.tf

output "cluster_name" {
  value = aws_eks_cluster.this.name
}

output "cluster_arn" {
  value = aws_eks_cluster.this.arn
}

output "cluster_endpoint" {
  value = aws_eks_cluster.this.endpoint
}

output "cluster_certificate_authority_data" {
  value = aws_eks_cluster.this.certificate_authority[0].data
}

output "cluster_version" {
  value = aws_eks_cluster.this.version
}

output "oidc_provider_arn" {
  value = aws_iam_openid_connect_provider.cluster.arn
}

output "oidc_provider_url" {
  value = aws_iam_openid_connect_provider.cluster.url
}

output "cluster_primary_security_group_id" {
  description = "EKS-managed cluster security group, shared by control plane and managed-node-group nodes — use this as the ingress source for RDS/ElastiCache security groups."
  value       = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
}

output "node_role_arn" {
  value = aws_iam_role.node.arn
}

output "secrets_kms_key_arn" {
  description = "KMS key used for EKS Secrets envelope encryption — also usable as the Secrets Manager KMS key for consistency, if desired."
  value       = aws_kms_key.eks_secrets.arn
}

output "cluster_autoscaler_role_arn" {
  description = "IRSA role ARN for the cluster-autoscaler ServiceAccount (kube-system/cluster-autoscaler) — scaffolding only, not yet installed as a workload."
  value       = aws_iam_role.cluster_autoscaler.arn
}

output "aws_lb_controller_role_arn" {
  description = "IRSA role ARN for the AWS Load Balancer Controller ServiceAccount (kube-system/aws-load-balancer-controller) — scaffolding only, not yet installed as a workload."
  value       = aws_iam_role.aws_lb_controller.arn
}
