# infra/terraform/environments/dev/namespace.tf
#
# Truly environment-unique (implementation plan item 9,
# .claude/skills/terraform-conventions/SKILL.md's exception for
# environment-only resources): a single shared namespace per environment
# (docs/containerization-and-orchestration.md section 3.3), not
# per-service, plus its default-deny-ingress NetworkPolicy baseline. Each
# service's own chart adds only the explicit allow rules it needs on top
# of this default.
#
# Goes through the same `terraform plan` human-review gate as every other
# resource here — not a `kubectl apply` side-channel around that gate.

resource "kubernetes_namespace" "app" {
  metadata {
    name = var.namespace

    labels = {
      "nutriapp.io/environment" = var.environment
    }
  }

  depends_on = [
    module.eks,
  ]
}

resource "kubernetes_network_policy" "default_deny_ingress" {
  metadata {
    name      = "default-deny-ingress"
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  spec {
    pod_selector {}
    policy_types = ["Ingress"]
    # Empty ingress block = deny all ingress by default. Each service's
    # Helm chart adds its own NetworkPolicy (via _lib's _networkpolicy.tpl)
    # allowing only the specific traffic it needs (from Kong, from named
    # peer services, from Prometheus).
  }
}
