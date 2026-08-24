# infra/terraform/modules/eks/node_groups.tf
#
# Two managed node groups: on-demand baseline capacity + spot burst
# capacity for interruption-tolerant, non-critical workloads (e.g. async
# event projectors), per docs/terraform-and-infrastructure.md section 3.

resource "aws_iam_role" "node" {
  name = "${var.cluster_name}-eks-node"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.base_tags
}

resource "aws_iam_role_policy_attachment" "node_worker" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "node_cni" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "node_ecr" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_eks_node_group" "on_demand" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.cluster_name}-on-demand"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.private_subnet_ids

  capacity_type  = var.capacity_type_on_demand
  instance_types = var.on_demand_instance_types
  ami_type       = var.ami_type

  scaling_config {
    desired_size = var.on_demand_desired_size
    min_size     = var.on_demand_min_size
    max_size     = var.on_demand_max_size
  }

  update_config {
    max_unavailable = 1
  }

  labels = {
    "nutriapp.io/capacity-type" = "on-demand"
  }

  tags = merge(local.base_tags, {
    Name = "${var.cluster_name}-on-demand"
    # Required by cluster-autoscaler to discover this node group via its
    # own IRSA-scoped autoscaling:DescribeTags permission (iam.tf).
    "k8s.io/cluster-autoscaler/enabled"             = "true"
    "k8s.io/cluster-autoscaler/${var.cluster_name}" = "owned"
  })

  depends_on = [
    aws_iam_role_policy_attachment.node_worker,
    aws_iam_role_policy_attachment.node_cni,
    aws_iam_role_policy_attachment.node_ecr,
  ]

  lifecycle {
    ignore_changes = [scaling_config[0].desired_size]
  }
}

resource "aws_eks_node_group" "spot" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.cluster_name}-spot"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.private_subnet_ids

  capacity_type  = "SPOT"
  instance_types = var.spot_instance_types
  ami_type       = var.ami_type

  scaling_config {
    desired_size = var.spot_desired_size
    min_size     = var.spot_min_size
    max_size     = var.spot_max_size
  }

  update_config {
    max_unavailable = 1
  }

  labels = {
    "nutriapp.io/capacity-type" = "spot"
  }

  taint {
    key    = "nutriapp.io/spot"
    value  = "true"
    effect = "PREFER_NO_SCHEDULE"
  }

  tags = merge(local.base_tags, {
    Name                                            = "${var.cluster_name}-spot"
    "k8s.io/cluster-autoscaler/enabled"             = "true"
    "k8s.io/cluster-autoscaler/${var.cluster_name}" = "owned"
  })

  depends_on = [
    aws_iam_role_policy_attachment.node_worker,
    aws_iam_role_policy_attachment.node_cni,
    aws_iam_role_policy_attachment.node_ecr,
  ]

  lifecycle {
    ignore_changes = [scaling_config[0].desired_size]
  }
}
