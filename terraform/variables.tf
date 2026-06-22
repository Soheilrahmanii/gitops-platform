variable "team_name" {
  description = "Team that owns this environment. Lowercase alphanumeric + hyphens, 3-40 chars."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,38}[a-z0-9]$", var.team_name))
    error_message = "team_name must be lowercase alphanumeric with hyphens, 3-40 chars, starting with a letter."
  }
}

variable "app_name" {
  description = "Application name. Lowercase alphanumeric + hyphens, 3-40 chars."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,38}[a-z0-9]$", var.app_name))
    error_message = "app_name must be lowercase alphanumeric with hyphens, 3-40 chars, starting with a letter."
  }
}

variable "kubeconfig_path" {
  description = "Path to the kubeconfig file. Defaults to the standard ~/.kube/config."
  type        = string
  default     = "~/.kube/config"
}

variable "kubeconfig_context" {
  description = "kubeconfig context to use. Defaults to the current active context."
  type        = string
  default     = null
}
