# Qdrant module -- the FIRST vector-store footprint in this repo
# (nutrition-assistant-service implementation plan section 9 resolution
# 3: "shared platform-level instance... since only one service uses it
# under the current spec"). Self-hosted via Helm inside the EKS cluster,
# per CLAUDE.md section 2.5 ("Qdrant for any vector-based RAG read model")
# and ARCHITECTURE.md's diagram (`ARCHITECTURE.md`: "Qdrant (Helm, if AI
# assistant)") -- never Qdrant Cloud, never a separately-billed managed
# service.
#
# Unlike modules/rds or modules/elasticache, there is no AWS-managed
# resource here at all -- this module's only job is the Helm release
# wiring, same shape every service's own `helm_release.<service>_service`
# resource already uses, just not scoped to one service's own chart.
#
# No precedent to mirror: RabbitMQ (this repo's other Helm-deployed
# platform dependency, per ARCHITECTURE.md's diagram) has NO Terraform
# footprint anywhere in this repo today -- flagged for architecture-agent
# review as a real, pre-existing gap this module does not attempt to fix
# (out of scope for nutrition-assistant-service's own plan).

resource "helm_release" "qdrant" {
  name      = var.release_name
  namespace = var.namespace
  chart     = "${path.module}/../../../k8s/charts/qdrant"
  version   = var.chart_version

  values = [
    yamlencode({
      replicaCount = var.replica_count
      persistence = {
        enabled = true
        size    = var.storage_size
      }
    })
  ]
}
