output "resource_name" {
  description = "Canonical name used across all provisioned resources."
  value       = local.resource_name
}

output "namespace_name" {
  description = "Kubernetes namespace created for this environment."
  value       = module.namespace.namespace_name
}

output "service_account_name" {
  description = "ServiceAccount granted developer RBAC in the namespace."
  value       = module.rbac.service_account_name
}

output "role_name" {
  description = "Role created in the namespace."
  value       = module.rbac.role_name
}
