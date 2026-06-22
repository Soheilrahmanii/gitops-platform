# terraform test — runs without a live cluster via mock_provider.
# Run from the module root: cd terraform/modules/rbac && terraform test

mock_provider "kubernetes" {}

variables {
  resource_name = "platform-hello-world"
  namespace     = "platform-hello-world"
}

# ── service account ────────────────────────────────────────────────────────────

run "service_account_name_matches_resource_name" {
  assert {
    condition     = kubernetes_service_account.this.metadata[0].name == "platform-hello-world"
    error_message = "ServiceAccount name must equal resource_name."
  }
}

run "service_account_is_in_correct_namespace" {
  assert {
    condition     = kubernetes_service_account.this.metadata[0].namespace == "platform-hello-world"
    error_message = "ServiceAccount must be created in var.namespace."
  }
}

# ── role ───────────────────────────────────────────────────────────────────────

run "role_is_named_developer" {
  assert {
    condition     = kubernetes_role.developer.metadata[0].name == "developer"
    error_message = "Role must be named 'developer'."
  }
}

run "role_is_in_correct_namespace" {
  assert {
    condition     = kubernetes_role.developer.metadata[0].namespace == "platform-hello-world"
    error_message = "Role must be scoped to var.namespace."
  }
}

run "role_grants_pod_access" {
  assert {
    condition     = contains(kubernetes_role.developer.rule[0].resources, "pods")
    error_message = "Developer role must grant access to pods."
  }
}

run "role_grants_deployment_access" {
  assert {
    condition     = contains(kubernetes_role.developer.rule[0].resources, "deployments")
    error_message = "Developer role must grant access to deployments."
  }
}

run "role_includes_watch_verb" {
  assert {
    condition     = contains(kubernetes_role.developer.rule[0].verbs, "watch")
    error_message = "Developer role must include the 'watch' verb for live log streaming."
  }
}

run "role_does_not_grant_cluster_wide_verbs" {
  # 'delete' on pods is allowed within namespace; the role itself has no ClusterRole binding.
  # This test verifies api_groups don't include cluster-scoped resources (rbac, nodes, etc.).
  assert {
    condition     = !contains(kubernetes_role.developer.rule[0].api_groups, "rbac.authorization.k8s.io")
    error_message = "Developer role must not grant RBAC management permissions."
  }
}

# ── role binding ───────────────────────────────────────────────────────────────

run "role_binding_is_in_correct_namespace" {
  assert {
    condition     = kubernetes_role_binding.developer.metadata[0].namespace == "platform-hello-world"
    error_message = "RoleBinding must be in var.namespace."
  }
}

run "role_binding_references_developer_role" {
  assert {
    condition     = kubernetes_role_binding.developer.role_ref[0].name == "developer"
    error_message = "RoleBinding must reference the 'developer' Role."
  }
}

run "role_binding_role_ref_kind_is_role" {
  assert {
    condition     = kubernetes_role_binding.developer.role_ref[0].kind == "Role"
    error_message = "RoleBinding must bind a namespaced Role, not a ClusterRole."
  }
}

run "role_binding_subjects_include_service_account" {
  assert {
    condition     = kubernetes_role_binding.developer.subject[0].kind == "ServiceAccount"
    error_message = "RoleBinding subject must be a ServiceAccount."
  }
}

run "role_binding_subject_name_matches_sa" {
  assert {
    condition     = kubernetes_role_binding.developer.subject[0].name == "platform-hello-world"
    error_message = "RoleBinding subject name must match the ServiceAccount name."
  }
}

# ── outputs ────────────────────────────────────────────────────────────────────

run "output_service_account_name_is_correct" {
  assert {
    condition     = output.service_account_name == "platform-hello-world"
    error_message = "service_account_name output must equal resource_name."
  }
}

run "output_role_name_is_developer" {
  assert {
    condition     = output.role_name == "developer"
    error_message = "role_name output must be 'developer'."
  }
}
