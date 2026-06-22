locals {
  # Single canonical identifier used for every K8s resource created in this apply.
  # Stored as a local (not a variable) so modules always derive it the same way.
  resource_name = "${var.team_name}-${var.app_name}"
}
