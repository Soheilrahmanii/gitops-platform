# terraform test — runs without a live cluster via mock_provider.
# Run from the module root: cd terraform/modules/namespace && terraform test

mock_provider "kubernetes" {}

variables {
  resource_name = "platform-hello-world"
  team_name     = "platform"
  app_name      = "hello-world"
}

# ── namespace ──────────────────────────────────────────────────────────────────

run "namespace_name_matches_resource_name" {
  assert {
    condition     = kubernetes_namespace.this.metadata[0].name == "platform-hello-world"
    error_message = "Namespace name must equal resource_name."
  }
}

run "namespace_has_managed_by_label" {
  assert {
    condition     = kubernetes_namespace.this.metadata[0].labels["managed-by"] == "idp"
    error_message = "Namespace must carry the 'managed-by=idp' label."
  }
}

run "namespace_team_label_matches_team_name" {
  assert {
    condition     = kubernetes_namespace.this.metadata[0].labels["team"] == "platform"
    error_message = "Namespace 'team' label must match var.team_name."
  }
}

run "namespace_app_label_matches_app_name" {
  assert {
    condition     = kubernetes_namespace.this.metadata[0].labels["app"] == "hello-world"
    error_message = "Namespace 'app' label must match var.app_name."
  }
}

# ── resource quota ─────────────────────────────────────────────────────────────

run "quota_lives_in_correct_namespace" {
  assert {
    condition     = kubernetes_resource_quota.this.metadata[0].namespace == "platform-hello-world"
    error_message = "ResourceQuota must be in the same namespace as the Namespace resource."
  }
}

run "quota_caps_pods_at_ten" {
  assert {
    condition     = kubernetes_resource_quota.this.spec[0].hard["pods"] == "10"
    error_message = "Pod quota must be capped at 10 for demo clusters."
  }
}

run "quota_sets_cpu_request_limit" {
  assert {
    condition     = kubernetes_resource_quota.this.spec[0].hard["requests.cpu"] == "500m"
    error_message = "CPU request quota must be 500m."
  }
}

run "quota_sets_memory_limit" {
  assert {
    condition     = kubernetes_resource_quota.this.spec[0].hard["limits.memory"] == "1Gi"
    error_message = "Memory limit quota must be 1Gi."
  }
}

# ── limit range ────────────────────────────────────────────────────────────────

run "limit_range_lives_in_correct_namespace" {
  assert {
    condition     = kubernetes_limit_range.this.metadata[0].namespace == "platform-hello-world"
    error_message = "LimitRange must be in the same namespace."
  }
}

run "limit_range_default_cpu_is_set" {
  assert {
    condition     = kubernetes_limit_range.this.spec[0].limit[0].default["cpu"] == "100m"
    error_message = "Default CPU limit must be 100m so containers without limits are bounded."
  }
}

run "limit_range_default_memory_is_set" {
  assert {
    condition     = kubernetes_limit_range.this.spec[0].limit[0].default["memory"] == "128Mi"
    error_message = "Default memory limit must be 128Mi."
  }
}

# ── outputs ────────────────────────────────────────────────────────────────────

run "output_namespace_name_is_correct" {
  assert {
    condition     = output.namespace_name == "platform-hello-world"
    error_message = "namespace_name output must equal resource_name."
  }
}
