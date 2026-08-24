# infra/terraform/modules/vpc/main.tf
#
# 3-AZ VPC: public subnets (ALB, NAT gateways only) and private subnets
# (EKS nodes, RDS, ElastiCache, and future RabbitMQ/Qdrant) — no
# database or internal service ever sits in a public subnet, per
# docs/terraform-and-infrastructure.md section 3.

locals {
  az_count = length(var.availability_zones)

  base_tags = merge(var.tags, {
    Service = "shared"
  })

  cluster_discovery_tags = var.cluster_name == null ? {} : {
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  }
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(local.base_tags, {
    Name = var.name
  })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = merge(local.base_tags, {
    Name = "${var.name}-igw"
  })
}

resource "aws_subnet" "public" {
  count             = local.az_count
  vpc_id            = aws_vpc.this.id
  cidr_block        = var.public_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]
  # No auto-assigned public IP: the only resources placed here (NAT
  # gateways, and future ALBs via the AWS Load Balancer Controller) get
  # their own explicit public IP/EIP already — nothing launched into
  # this subnet needs one by default (checkov CKV_AWS_130).
  map_public_ip_on_launch = false

  tags = merge(local.base_tags, local.cluster_discovery_tags, {
    Name                     = "${var.name}-public-${var.availability_zones[count.index]}"
    Tier                     = "public"
    "kubernetes.io/role/elb" = "1"
  })
}

resource "aws_subnet" "private" {
  count             = local.az_count
  vpc_id            = aws_vpc.this.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = merge(local.base_tags, local.cluster_discovery_tags, {
    Name                              = "${var.name}-private-${var.availability_zones[count.index]}"
    Tier                              = "private"
    "kubernetes.io/role/internal-elb" = "1"
  })
}

# --- NAT --------------------------------------------------------------
# single_nat_gateway=true (dev default) trades AZ-level HA for cost: if
# the NAT gateway's AZ has an outage, private-subnet egress in the other
# AZs is also lost. Accepted for `dev` per
# docs/terraform-and-infrastructure.md section 3 / the implementation
# plan's cost table. staging/prod must set this to false.

resource "aws_eip" "nat" {
  count  = var.single_nat_gateway ? 1 : local.az_count
  domain = "vpc"

  tags = merge(local.base_tags, {
    Name = "${var.name}-nat-eip-${count.index}"
  })

  depends_on = [aws_internet_gateway.this]
}

resource "aws_nat_gateway" "this" {
  count         = var.single_nat_gateway ? 1 : local.az_count
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = merge(local.base_tags, {
    Name = "${var.name}-nat-${count.index}"
  })

  depends_on = [aws_internet_gateway.this]
}

# --- Routing ------------------------------------------------------------

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  tags = merge(local.base_tags, {
    Name = "${var.name}-public-rt"
  })
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table_association" "public" {
  count          = local.az_count
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  count  = var.single_nat_gateway ? 1 : local.az_count
  vpc_id = aws_vpc.this.id

  tags = merge(local.base_tags, {
    Name = "${var.name}-private-rt-${count.index}"
  })
}

resource "aws_route" "private_nat" {
  count                  = var.single_nat_gateway ? 1 : local.az_count
  route_table_id         = aws_route_table.private[count.index].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.this[count.index].id
}

resource "aws_route_table_association" "private" {
  count          = local.az_count
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = var.single_nat_gateway ? aws_route_table.private[0].id : aws_route_table.private[count.index].id
}

# --- Default security group: locked down, unused by design --------------
# Nothing in this VPC uses the VPC's auto-created default security group —
# every resource module (eks, rds, elasticache) creates and attaches its
# own explicit, narrowly-scoped security group. Explicitly managing the
# default SG down to zero rules prevents it from silently becoming an
# escape hatch if a future resource is created without an explicit SG
# (checkov CKV2_AWS_12).
resource "aws_default_security_group" "this" {
  vpc_id = aws_vpc.this.id

  # Explicit empty ingress/egress lists are required for Terraform to
  # actively remove AWS's automatically-created default rules (an empty
  # `aws_default_security_group` block with no ingress/egress arguments
  # at all leaves those default rules unmanaged, not removed).
  ingress = []
  egress  = []

  tags = merge(local.base_tags, {
    Name = "${var.name}-default-locked-down"
  })
}

# --- VPC Flow Logs --------------------------------------------------------
# Audit trail for network access (CLAUDE.md section 2.8's audit-trail
# requirement extends naturally to network-level access, not just
# application events). Short retention (14 days, matching the
# scale-to-zero Lambda's log retention) to bound CloudWatch Logs storage
# cost for a low-traffic dev VPC (checkov CKV2_AWS_11).
resource "aws_cloudwatch_log_group" "vpc_flow_logs" {
  name              = "/nutriapp/${var.name}/vpc-flow-logs"
  retention_in_days = 14

  tags = local.base_tags

  # checkov:skip=CKV_AWS_338:14-day retention bounds CloudWatch Logs storage cost for a dev VPC's flow logs; 1-year retention has a real ongoing cost with no corresponding compliance requirement at this project's current stage (ADR-0020 — no formal certification pursued yet).
  # checkov:skip=CKV_AWS_158:Default CloudWatch Logs encryption (AWS-owned key) already applies; a dedicated CMK is disproportionate for flow-log metadata (source/dest IP, port, protocol — no payload data, no secrets).
}

resource "aws_iam_role" "vpc_flow_logs" {
  name = "${var.name}-vpc-flow-logs"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "vpc-flow-logs.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.base_tags
}

resource "aws_iam_role_policy" "vpc_flow_logs" {
  name = "publish-flow-logs"
  role = aws_iam_role.vpc_flow_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
        ]
        Resource = "${aws_cloudwatch_log_group.vpc_flow_logs.arn}:*"
      }
    ]
  })
}

resource "aws_flow_log" "this" {
  vpc_id               = aws_vpc.this.id
  traffic_type         = "ALL"
  log_destination_type = "cloud-watch-logs"
  log_destination      = aws_cloudwatch_log_group.vpc_flow_logs.arn
  iam_role_arn         = aws_iam_role.vpc_flow_logs.arn

  tags = merge(local.base_tags, {
    Name = "${var.name}-flow-logs"
  })
}
