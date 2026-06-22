#!/usr/bin/env bash
# Bootstraps a local kind cluster with ArgoCD and Grafana.
# Run once before starting docker-compose.
set -euo pipefail

CLUSTER_NAME="gitops-platform"
ARGOCD_VERSION="v2.10.5"

echo "==> Creating kind cluster: $CLUSTER_NAME"
cat <<EOF | kind create cluster --name "$CLUSTER_NAME" --config=- --wait 60s
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  apiServerAddress: "0.0.0.0"
EOF

echo "==> Installing ArgoCD $ARGOCD_VERSION"
kubectl create namespace argocd
kubectl apply -n argocd \
  -f "https://raw.githubusercontent.com/argoproj/argo-cd/$ARGOCD_VERSION/manifests/install.yaml"

echo "==> Waiting for ArgoCD server to be ready..."
kubectl rollout status deploy/argocd-server -n argocd --timeout=120s

# Print the initial admin password so it lands in the setup output.
ARGOCD_PASSWORD=$(kubectl get secret argocd-initial-admin-secret \
  -n argocd -o jsonpath="{.data.password}" | base64 -d)
echo ""
echo "ArgoCD admin password: $ARGOCD_PASSWORD"
echo "Access: kubectl port-forward svc/argocd-server -n argocd 8443:443"

echo "==> Installing kube-prometheus-stack (Grafana included)"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  --set grafana.adminPassword=admin \
  --wait --timeout 5m

echo ""
echo "Grafana admin password: admin"
echo "Access: kubectl port-forward svc/monitoring-grafana -n monitoring 3001:80 &"
echo ""
echo "==> Starting Grafana port-forward on :3001 in background..."
kubectl port-forward svc/monitoring-grafana -n monitoring 3001:80 &
echo "==> Cluster ready. Run: docker compose up --build"
