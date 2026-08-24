# infra/terraform/modules/eks/main.tf
#
# EKS cluster, on-demand + spot managed node groups, IRSA/OIDC provider.
# Per ADR-0006: no service mesh, Helm-deployed workloads, cluster
# controllers (cluster-autoscaler, AWS Load Balancer Controller, ESO) get
# IRSA/IAM scaffolding here but are NOT installed as running workloads by
# this module — that's devops-agent CI/CD territory (implementation plan
# section 1, "explicitly out of scope").

locals {
  base_tags = merge(var.tags, {
    Service = "shared"
  })
}

# --- Cluster IAM ---------------------------------------------------------

resource "aws_iam_role" "cluster" {
  name = "${var.cluster_name}-eks-cluster"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.base_tags
}

resource "aws_iam_role_policy_attachment" "cluster_policy" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

# --- Cluster ---------------------------------------------------------------

resource "aws_security_group" "cluster_additional" {
  name        = "${var.cluster_name}-eks-additional"
  description = "Additional security group for the EKS cluster (beyond the EKS-managed cluster SG), reserved for future rules."
  vpc_id      = var.vpc_id

  tags = merge(local.base_tags, {
    Name = "${var.cluster_name}-eks-additional"
  })
}

data "aws_caller_identity" "current" {}

# Envelope encryption of Kubernetes Secret objects at rest in etcd —
# directly relevant since External Secrets Operator (ADR-0007) syncs
# Secrets Manager values into native k8s Secret objects that live in
# etcd (checkov CKV_AWS_58). Small, flat KMS cost (~$1/mo).
#
# Explicit key policy (rather than relying on AWS's implicit default):
# account root retains full IAM-delegated management (standard practice —
# lets ordinary IAM policies, not just this one resource policy, govern
# access), and the EKS cluster's own service role is granted exactly the
# grant/describe/decrypt permissions EKS needs to use this key.
#
# `Resource: "*"` below is standard, required KMS *key policy* syntax —
# in a resource-based KMS key policy (unlike an IAM identity policy),
# "*" is self-referential to "this key" (the key the policy is attached
# to), not "every KMS key in the account". There is no tighter,
# more-specific ARN to constrain this to.
# checkov:skip=CKV_AWS_109:KMS key policy, not an identity policy — "*" here means "this key only" (AWS-required syntax), not account-wide permissions-management exposure.
# checkov:skip=CKV_AWS_356:Same KMS key-policy syntax note as above.
# checkov:skip=CKV_AWS_111:Same KMS key-policy syntax note as above — the EksClusterServiceRoleUsage statement is already scoped to a single named principal (the cluster's own IAM role), just not a narrower resource ARN, which key policies don't support.
# checkov:skip=CKV2_AWS_64:Key policy is explicitly defined below (this check appears to fire on the pre-refactor data-source shape; kept for visibility in case of a checkov version-specific gap).
resource "aws_kms_key" "eks_secrets" {
  description             = "EKS Secrets envelope encryption for ${var.cluster_name}"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AccountRootFullAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "EksClusterServiceRoleUsage"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.cluster.arn
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:CreateGrant",
        ]
        Resource = "*"
      },
    ]
  })

  tags = merge(local.base_tags, {
    Name = "${var.cluster_name}-eks-secrets"
  })
}

resource "aws_kms_alias" "eks_secrets" {
  name          = "alias/${var.cluster_name}-eks-secrets"
  target_key_id = aws_kms_key.eks_secrets.key_id
}

resource "aws_eks_cluster" "this" {
  name     = var.cluster_name
  role_arn = aws_iam_role.cluster.arn
  version  = var.kubernetes_version

  vpc_config {
    subnet_ids              = concat(var.private_subnet_ids, var.public_subnet_ids)
    endpoint_private_access = true
    # Public endpoint access, restricted to var.cluster_endpoint_public_access_cidrs
    # (never 0.0.0.0/0 — enforced by that variable's validation block):
    # resolved decision, implementation plan section 9.3 — simpler for
    # solo/dev work than a permanent bastion/VPN, at the cost of needing
    # periodic manual CIDR updates as the operator's IP changes.
    # checkov:skip=CKV_AWS_39:Resolved decision, implementation plan section 9.3 — public+private access restricted to an explicit CIDR allowlist (never 0.0.0.0/0), not a bare public endpoint.
    endpoint_public_access = true
    public_access_cidrs    = var.cluster_endpoint_public_access_cidrs
    security_group_ids     = [aws_security_group.cluster_additional.id]
  }

  encryption_config {
    resources = ["secrets"]
    provider {
      key_arn = aws_kms_key.eks_secrets.arn
    }
  }

  # api+audit only (not scheduler/authenticator/controllerManager) for
  # dev cost — each enabled log type adds CloudWatch Logs ingestion cost
  # proportional to cluster activity; api+audit cover the
  # security-relevant "who did what" audit trail this project's
  # CLAUDE.md section 2.8 cares most about. Revisit for staging/prod.
  # checkov:skip=CKV_AWS_37:Dev cost decision — api+audit cover the audit-trail need; full log types revisited for staging/prod (docs/cost-management.md).
  enabled_cluster_log_types = ["api", "audit"]

  access_config {
    authentication_mode                         = "API_AND_CONFIG_MAP"
    bootstrap_cluster_creator_admin_permissions = true
  }

  tags = merge(local.base_tags, {
    Name = var.cluster_name
  })

  depends_on = [
    aws_iam_role_policy_attachment.cluster_policy,
  ]
}

# --- IRSA / OIDC -----------------------------------------------------------

data "tls_certificate" "cluster_oidc" {
  url = aws_eks_cluster.this.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "cluster" {
  url             = aws_eks_cluster.this.identity[0].oidc[0].issuer
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.cluster_oidc.certificates[0].sha1_fingerprint]

  tags = local.base_tags
}
