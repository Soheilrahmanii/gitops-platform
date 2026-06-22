terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.29"
    }
  }
}

resource "kubernetes_namespace" "this" {
  metadata {
    name = var.resource_name
    labels = {
      "managed-by" = "idp"
      "team"        = var.team_name
      "app"         = var.app_name
    }
  }
}

# Hard ceiling so one team can't starve the whole cluster in a demo.
resource "kubernetes_resource_quota" "this" {
  metadata {
    name      = "default-quota"
    namespace = kubernetes_namespace.this.metadata[0].name
  }

  spec {
    hard = {
      "requests.cpu"    = "500m"
      "requests.memory" = "512Mi"
      "limits.cpu"      = "1"
      "limits.memory"   = "1Gi"
      "pods"            = "10"
    }
  }
}

# Ensure containers without explicit resource limits don't inherit node-level limits,
# which would make scheduling unpredictable in a shared demo cluster.
resource "kubernetes_limit_range" "this" {
  metadata {
    name      = "default-limits"
    namespace = kubernetes_namespace.this.metadata[0].name
  }

  spec {
    limit {
      type = "Container"
      default = {
        cpu    = "100m"
        memory = "128Mi"
      }
      default_request = {
        cpu    = "50m"
        memory = "64Mi"
      }
    }
  }
}
