terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.29"
    }
  }
}

resource "kubernetes_service_account" "this" {
  metadata {
    name      = var.resource_name
    namespace = var.namespace
  }
}

# Developer role: read/write workloads but no cluster-level access.
resource "kubernetes_role" "developer" {
  metadata {
    name      = "developer"
    namespace = var.namespace
  }

  rule {
    api_groups = ["", "apps", "batch"]
    resources  = ["pods", "deployments", "services", "configmaps", "jobs", "cronjobs"]
    verbs      = ["get", "list", "watch", "create", "update", "patch", "delete"]
  }

  rule {
    api_groups = [""]
    resources  = ["pods/log", "pods/exec"]
    verbs      = ["get", "list"]
  }
}

resource "kubernetes_role_binding" "developer" {
  metadata {
    name      = "developer-binding"
    namespace = var.namespace
  }

  role_ref {
    api_group = "rbac.authorization.k8s.io"
    kind      = "Role"
    name      = kubernetes_role.developer.metadata[0].name
  }

  subject {
    kind      = "ServiceAccount"
    name      = kubernetes_service_account.this.metadata[0].name
    namespace = var.namespace
  }
}
