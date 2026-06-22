#!/usr/bin/env bash
# Destroys the kind cluster and removes local Terraform state files.
set -euo pipefail

CLUSTER_NAME="gitops-platform"

echo "==> Deleting kind cluster: $CLUSTER_NAME"
kind delete cluster --name "$CLUSTER_NAME"

echo "==> Removing Terraform state files"
find "$(dirname "$0")/../terraform" -name "*.tfstate*" -delete
find "$(dirname "$0")/../terraform" -name ".terraform" -type d -exec rm -rf {} + 2>/dev/null || true

echo "==> Done. GitHub repos created during testing must be deleted manually."
