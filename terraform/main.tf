terraform {
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.29"
    }
  }
  required_version = ">= 1.7"
}

# config_path defaults to the standard location so docker-compose works without
# setting KUBECONFIG, but CI or multi-cluster setups can override it.
provider "kubernetes" {
  config_path = var.kubeconfig_path
}

module "namespace" {
  source        = "./modules/namespace"
  resource_name = local.resource_name
  team_name     = var.team_name
  app_name      = var.app_name
}

module "rbac" {
  source        = "./modules/rbac"
  resource_name = local.resource_name
  namespace     = module.namespace.namespace_name
}
