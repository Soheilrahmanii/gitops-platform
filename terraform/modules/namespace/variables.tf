variable "resource_name" {
  description = "Canonical resource name (team-app). Used as the namespace name and in labels."
  type        = string
}

variable "team_name" {
  description = "Team that owns this namespace. Used in the 'team' label."
  type        = string
}

variable "app_name" {
  description = "Application name. Used in the 'app' label."
  type        = string
}
