output "qdrant_url" {
  description = "In-cluster HTTP URL every consuming service's NUTRITION_ASSISTANT_SERVICE_QDRANT_URL env var is set to -- standard Kubernetes Service DNS, same namespace as the release."
  value       = "http://${var.release_name}.${var.namespace}.svc.cluster.local:6333"
}

output "release_name" {
  value = helm_release.qdrant.name
}
