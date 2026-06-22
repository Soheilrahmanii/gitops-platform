output "namespace_name" {
  description = "Name of the created Kubernetes namespace."
  value       = kubernetes_namespace.this.metadata[0].name
}

output "quota_name" {
  description = "Name of the ResourceQuota in the namespace."
  value       = kubernetes_resource_quota.this.metadata[0].name
}

output "limit_range_name" {
  description = "Name of the LimitRange in the namespace."
  value       = kubernetes_limit_range.this.metadata[0].name
}
