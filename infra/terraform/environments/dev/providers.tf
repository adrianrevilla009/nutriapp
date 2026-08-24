# infra/terraform/environments/dev/providers.tf

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "nutriapp"
      Environment = var.environment
      ManagedBy   = "terraform"
      CostCenter  = "platform-shared"
    }
  }
}

# Used by kubernetes_namespace / kubernetes_network_policy below (item 9
# of the implementation plan). Auth is via `aws eks get-token`, requiring
# the AWS CLI and valid AWS credentials for whoever runs `terraform
# plan`/`apply` — consistent with humans/CI already needing AWS
# credentials to run Terraform at all.
provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name, "--region", var.aws_region]
  }
}

# Used by identity-service.tf's helm_release.identity_service (and every
# future service's own helm_release, same pattern). Without this explicit
# block the helm provider defaults to ambient local kubeconfig, which
# does not point at this cluster — same auth mechanism as the kubernetes
# provider above, deliberately kept identical rather than drifting.
provider "helm" {
  kubernetes = {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

    exec = {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name, "--region", var.aws_region]
    }
  }
}
