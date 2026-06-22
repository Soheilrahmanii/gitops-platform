#!/usr/bin/env bash
# Validates the app-template Helm chart without a live cluster.
# Uses 'helm lint' (syntax) and 'helm template' (render) to catch issues early.
set -euo pipefail

CHART_DIR="$(cd "$(dirname "$0")/../gitops/apps/app-template" && pwd)"

echo "==> helm lint"
helm lint "$CHART_DIR" --strict

echo ""
echo "==> helm template (default values)"
helm template test-release "$CHART_DIR" \
  --namespace platform-hello-world \
  --set image.tag=v1.2.3 \
  | grep "^kind:" | sort

echo ""
echo "==> helm template (autoscaling enabled)"
helm template test-release "$CHART_DIR" \
  --namespace platform-hello-world \
  --set autoscaling.enabled=true \
  | grep "^kind:" | sort

echo ""
echo "==> helm template --dry-run (validates generated YAML parses cleanly)"
helm template test-release "$CHART_DIR" \
  --namespace platform-hello-world > /dev/null

echo ""
echo "All Helm checks passed."
