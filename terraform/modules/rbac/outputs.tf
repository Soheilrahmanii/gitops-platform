output "service_account_name" {
  description = "Name of the ServiceAccount granted developer permissions."
  value       = kubernetes_service_account.this.metadata[0].name
}

output "role_name" {
  description = "Name of the Role created in the namespace."
  value       = kubernetes_role.developer.metadata[0].name
}

output "role_binding_name" {
  description = "Name of the RoleBinding linking the SA to the Role."
  value       = kubernetes_role_binding.developer.metadata[0].name
}
