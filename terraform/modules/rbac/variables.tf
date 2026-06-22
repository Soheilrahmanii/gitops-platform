variable "resource_name" {
  description = "Canonical resource name (team-app). Used as the ServiceAccount name."
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace in which to create the Role and RoleBinding."
  type        = string
}
