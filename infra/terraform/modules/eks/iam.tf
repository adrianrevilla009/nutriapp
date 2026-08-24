# infra/terraform/modules/eks/iam.tf
#
# IRSA (IAM Roles for Service Accounts) scaffolding for cluster-wide
# controllers. Per the implementation plan section 3 item "explicitly out
# of scope", this module provisions the IAM role + trust policy only —
# the actual `helm install` of cluster-autoscaler / AWS Load Balancer
# Controller is devops-agent CI/CD territory, a later follow-up. The
# expected Kubernetes ServiceAccount name/namespace is fixed here as the
# convention those future Helm releases must use to match the trust
# policy's `sub` condition.

locals {
  oidc_provider_url = replace(aws_iam_openid_connect_provider.cluster.url, "https://", "")

  cluster_autoscaler_namespace       = "kube-system"
  cluster_autoscaler_service_account = "cluster-autoscaler"

  aws_lb_controller_namespace       = "kube-system"
  aws_lb_controller_service_account = "aws-load-balancer-controller"
}

# --- cluster-autoscaler ------------------------------------------------

data "aws_iam_policy_document" "cluster_autoscaler_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.cluster.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider_url}:sub"
      values   = ["system:serviceaccount:${local.cluster_autoscaler_namespace}:${local.cluster_autoscaler_service_account}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "cluster_autoscaler" {
  name               = "${var.cluster_name}-cluster-autoscaler"
  assume_role_policy = data.aws_iam_policy_document.cluster_autoscaler_assume.json

  tags = local.base_tags
}

data "aws_iam_policy_document" "cluster_autoscaler" {
  # Read-only Describe* actions: AWS does not support resource-level ARN
  # restriction for these (the standard, upstream-documented shape of the
  # cluster-autoscaler IAM policy — https://github.com/kubernetes/autoscaler/
  # blob/master/cluster-autoscaler/cloudprovider/aws/README.md).
  # checkov:skip=CKV_AWS_356:Describe* actions require resource "*" (AWS API limitation, not a scoping choice) — the actual mutating actions below ARE scoped via the aws:ResourceTag condition, matching the upstream cluster-autoscaler least-privilege policy pattern.
  # checkov:skip=CKV_AWS_111:See above — mutating actions (SetDesiredCapacity, TerminateInstanceInAutoScalingGroup) are tag-conditioned below, not unconstrained.
  statement {
    sid    = "DescribeOnly"
    effect = "Allow"
    actions = [
      "autoscaling:DescribeAutoScalingGroups",
      "autoscaling:DescribeAutoScalingInstances",
      "autoscaling:DescribeLaunchConfigurations",
      "autoscaling:DescribeTags",
      "ec2:DescribeLaunchTemplateVersions",
      "eks:DescribeNodegroup",
    ]
    resources = ["*"]
  }

  # Mutating actions: scoped via the AWS-documented tag-condition pattern
  # to only the ASGs backing THIS cluster's node groups (tagged
  # k8s.io/cluster-autoscaler/<cluster-name>=owned by
  # modules/eks/node_groups.tf), not every ASG in the account.
  statement {
    sid    = "MutateOwnedAutoScalingGroupsOnly"
    effect = "Allow"
    actions = [
      "autoscaling:SetDesiredCapacity",
      "autoscaling:TerminateInstanceInAutoScalingGroup",
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "autoscaling:ResourceTag/k8s.io/cluster-autoscaler/${var.cluster_name}"
      values   = ["owned"]
    }
  }
}

resource "aws_iam_role_policy" "cluster_autoscaler" {
  name   = "${var.cluster_name}-cluster-autoscaler"
  role   = aws_iam_role.cluster_autoscaler.id
  policy = data.aws_iam_policy_document.cluster_autoscaler.json
}

# --- AWS Load Balancer Controller ---------------------------------------

data "aws_iam_policy_document" "aws_lb_controller_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.cluster.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider_url}:sub"
      values   = ["system:serviceaccount:${local.aws_lb_controller_namespace}:${local.aws_lb_controller_service_account}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "aws_lb_controller" {
  name               = "${var.cluster_name}-aws-lb-controller"
  assume_role_policy = data.aws_iam_policy_document.aws_lb_controller_assume.json

  tags = local.base_tags
}

# NOTE: the AWS Load Balancer Controller's official IAM policy JSON is
# large (~150 lines) and versioned upstream. Rather than duplicating a
# copy here that will silently drift, this module scaffolds the
# assumable role only; devops-agent attaches the upstream policy
# (https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/main/docs/install/iam_policy.json)
# as an aws_iam_role_policy at controller-install time, pinned to the
# controller's chart version. Tracked as a deliberate scope boundary, not
# an oversight.
