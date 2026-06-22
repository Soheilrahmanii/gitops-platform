#!/usr/bin/env bash
# Validates Terraform syntax and runs native tests (no cluster required).
# Each module is tested in isolation first, then the root module is tested.
#
# Prerequisites: terraform >= 1.7 on PATH.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TF_DIR="$ROOT/terraform"

run_tests() {
  local dir="$1"
  local label="$2"
  echo ""
  echo "==> $label"
  terraform -chdir="$dir" init -backend=false -input=false -no-color 2>&1 | grep -v "^$"
  terraform -chdir="$dir" validate -no-color
  terraform -chdir="$dir" test -no-color
}

run_tests "$TF_DIR/modules/namespace" "namespace module"
run_tests "$TF_DIR/modules/rbac"     "rbac module"
run_tests "$TF_DIR"                  "root module"

echo ""
echo "All Terraform tests passed."
