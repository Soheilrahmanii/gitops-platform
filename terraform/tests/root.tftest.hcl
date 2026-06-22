# Root module integration test — validates that both modules wire together correctly.
# Run from: cd terraform && terraform test
# No live cluster required (mock_provider).

mock_provider "kubernetes" {}

variables {
  team_name = "platform"
  app_name  = "hello-world"
}

# ── local composition ──────────────────────────────────────────────────────────

run "resource_name_is_composed_from_team_and_app" {
  assert {
    condition     = output.resource_name == "platform-hello-world"
    error_message = "resource_name output must be '<team_name>-<app_name>'."
  }
}

# ── namespace module wiring ────────────────────────────────────────────────────

run "namespace_output_is_correct" {
  assert {
    condition     = output.namespace_name == "platform-hello-world"
    error_message = "namespace_name output must equal the composed resource_name."
  }
}

# ── rbac module wiring ─────────────────────────────────────────────────────────

run "service_account_output_is_correct" {
  assert {
    condition     = output.service_account_name == "platform-hello-world"
    error_message = "service_account_name output must equal the composed resource_name."
  }
}

run "role_output_is_developer" {
  assert {
    condition     = output.role_name == "developer"
    error_message = "role_name output must be 'developer'."
  }
}

# ── different team/app values ──────────────────────────────────────────────────

run "different_team_and_app_produce_correct_resource_name" {
  variables {
    team_name = "backend"
    app_name  = "payments-api"
  }

  assert {
    condition     = output.resource_name == "backend-payments-api"
    error_message = "resource_name must correctly combine any valid team/app pair."
  }

  assert {
    condition     = output.namespace_name == "backend-payments-api"
    error_message = "namespace_name must match for alternate team/app."
  }
}
