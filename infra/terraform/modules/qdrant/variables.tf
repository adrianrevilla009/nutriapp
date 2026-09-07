variable "namespace" {
  description = "Kubernetes namespace to deploy the shared Qdrant instance into (same app namespace every service's own Helm release deploys to, e.g. nutriapp-dev)."
  type        = string
}

variable "release_name" {
  description = "Helm release name -- also the in-cluster Service DNS name every consuming service's qdrant_url is derived from."
  type        = string
  default     = "nutrition-assistant-qdrant"
}

variable "chart_version" {
  type    = string
  default = "0.1.0"
}

variable "storage_size" {
  description = "PersistentVolumeClaim size for Qdrant's collection storage (dev sizing -- a single small collection's corpus this pass, per implementation plan section 9 resolution 2's small seed corpus)."
  type        = string
  default     = "5Gi"
}

variable "replica_count" {
  description = "Qdrant pod replica count. 1 for dev (no HA requirement yet -- this is a CQRS-style read model rebuildable from source per .claude/agents/nutrition-assistant-agent.md, so a dev-environment single-replica loss is recoverable by re-running infrastructure/vectorstore/seed_knowledge_base.py, not a data-loss event)."
  type        = number
  default     = 1
}

variable "tags" {
  type    = map(string)
  default = {}
}
