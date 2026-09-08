# frontend's Terraform footprint (implementation plan section 3/7) --
# mirrors bff-service.tf's zero-secret pattern exactly: an ECR repository
# for its own image, plus a bare IRSA role for its pod ServiceAccount.
# NOTHING else.
#
# This service has NO database (no `_db-provision-job` Helm hook, no
# entry in var.db_credential_service_names). It has NO secret of any
# kind: every call it makes (identity-service, catalog-service,
# diary-service, bff-service -- resolution 1's Route Handler proxies) is
# to an ordinary PUBLIC endpoint, forwarding either no credential
# (register/verify-email/login/catalog calls) or the caller's own
# already-issued access token (diary/bff calls) -- there is no credential
# to read from Secrets Manager, so this service is intentionally NOT
# wired through `module.secrets` at all, same reasoning as bff-service.tf.
#
# It still needs a ServiceAccount + IRSA role annotation, because
# infra/k8s/charts/_lib's `_serviceaccount.tpl` requires
# `serviceAccount.irsaRoleArn` unconditionally (ADR-0007's "every
# ServiceAccount has a scoped IRSA role" convention) -- defined here,
# self-contained, mirroring bff-service.tf's own self-contained IRSA
# role rather than extending `modules/secrets` for a one-off "a service
# with zero secrets" case.

locals {
  frontend_name                        = "frontend"
  frontend_namespace                   = "nutriapp-dev"
  frontend_oidc_provider_url_no_scheme = replace(module.eks.oidc_provider_url, "https://", "")
}

# --- ECR: this service's own app image ---
module "ecr_frontend" {
  source = "../../modules/ecr"

  repository_name = "nutriapp/${local.frontend_name}"

  tags = merge(local.common_tags, {
    Service = local.frontend_name
  })
}

# --- IRSA: app runtime, empty policy (no secret, no AWS permission of
# any kind needed) ---
data "aws_iam_policy_document" "frontend_app_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [module.eks.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.frontend_oidc_provider_url_no_scheme}:sub"
      values   = ["system:serviceaccount:${local.frontend_namespace}:${local.frontend_name}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.frontend_oidc_provider_url_no_scheme}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "frontend_app" {
  name               = "nutriapp-${var.environment}-${local.frontend_name}-app"
  assume_role_policy = data.aws_iam_policy_document.frontend_app_assume.json

  tags = merge(local.common_tags, {
    Service = local.frontend_name
  })
}

# Deliberately NO aws_iam_role_policy resource attached to the role
# above -- this service reads no secret and calls no AWS API.

# --- Helm release ---
resource "helm_release" "frontend" {
  name      = local.frontend_name
  namespace = local.frontend_namespace
  chart     = "${path.module}/../../../k8s/charts/frontend"
  version   = "0.1.0"

  values = [
    yamlencode({
      image = {
        # tag intentionally omitted -- set by frontend-ci.yml at deploy
        # time (`helm upgrade --set image.tag=$GIT_SHA`), never hardcoded
        # in Terraform, per ci-cd-conventions SKILL.md.
        repository = module.ecr_frontend.repository_url
      }
      serviceAccount = {
        irsaRoleArn = aws_iam_role.frontend_app.arn
      }
    })
  ]

  depends_on = [
    module.eks,
  ]
}
