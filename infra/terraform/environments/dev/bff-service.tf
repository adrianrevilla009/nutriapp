# bff-service's Terraform footprint (implementation plan section 3/7) --
# narrower than every prior service's .tf: an ECR repository for its own
# image, plus a bare IRSA role for its pod ServiceAccount. NOTHING else.
#
# This service has NO database (no `_db-provision-job` Helm hook, no
# entry in var.db_credential_service_names -- module.secrets'
# `app_secrets`/`db_provision` IAM roles are both keyed off that list and
# unconditionally reference an `aws_secretsmanager_secret.db_credentials`
# resource that only exists for services in it; adding bff-service there
# would incorrectly provision a database credential container it will
# never use). It has NO secret of any kind: every call it makes is to an
# ordinary PUBLIC endpoint (diary-service, nutrition-calculation-service),
# forwarding the caller's own JWT unchanged -- there is no credential to
# read from Secrets Manager, so this service is intentionally NOT wired
# through `module.secrets` at all.
#
# It still needs a ServiceAccount + IRSA role annotation, because
# infra/k8s/charts/_lib's `_serviceaccount.tpl` requires
# `serviceAccount.irsaRoleArn` unconditionally (ADR-0007's "every
# ServiceAccount has a scoped IRSA role" convention) -- defined here,
# self-contained, rather than extending the shared `modules/secrets`
# module for a one-off "a service with zero secrets" case (that shared-
# module shape change belongs to a separate, properly-scoped
# platform-infra initiative if a second zero-secret service ever needs
# it, not silently bolted on here). The trust policy mirrors
# `modules/secrets`' own db_provision/app_secrets role shape exactly,
# but with NO attached IAM policy at all -- least privilege taken to its
# logical conclusion: this role can be assumed by the pod, and can do
# nothing, because it needs to do nothing.

locals {
  bff_service_name                        = "bff-service"
  bff_service_namespace                   = "nutriapp-dev"
  bff_service_oidc_provider_url_no_scheme = replace(module.eks.oidc_provider_url, "https://", "")
}

# --- ECR: this service's own app image ---
module "ecr_bff_service" {
  source = "../../modules/ecr"

  repository_name = "nutriapp/${local.bff_service_name}"

  tags = merge(local.common_tags, {
    Service = local.bff_service_name
  })
}

# --- IRSA: app runtime, empty policy (no secret, no AWS permission of
# any kind needed) ---
data "aws_iam_policy_document" "bff_service_app_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [module.eks.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.bff_service_oidc_provider_url_no_scheme}:sub"
      values   = ["system:serviceaccount:${local.bff_service_namespace}:${local.bff_service_name}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.bff_service_oidc_provider_url_no_scheme}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "bff_service_app" {
  name               = "nutriapp-${var.environment}-${local.bff_service_name}-app"
  assume_role_policy = data.aws_iam_policy_document.bff_service_app_assume.json

  tags = merge(local.common_tags, {
    Service = local.bff_service_name
  })
}

# Deliberately NO aws_iam_role_policy resource attached to the role
# above -- this service reads no secret and calls no AWS API.

# --- Helm release ---
resource "helm_release" "bff_service" {
  name      = local.bff_service_name
  namespace = local.bff_service_namespace
  chart     = "${path.module}/../../../k8s/charts/bff-service"
  version   = "0.1.0"

  values = [
    yamlencode({
      image = {
        # tag intentionally omitted -- set by bff-service-ci.yml at
        # deploy time (`helm upgrade --set image.tag=$GIT_SHA`), never
        # hardcoded in Terraform, per ci-cd-conventions SKILL.md.
        repository = module.ecr_bff_service.repository_url
      }
      serviceAccount = {
        irsaRoleArn = aws_iam_role.bff_service_app.arn
      }
    })
  ]

  depends_on = [
    module.eks,
  ]
}
