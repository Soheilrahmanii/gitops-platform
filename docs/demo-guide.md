# Demo Guide

End-to-end walkthrough from a cold machine to a working provision demo.
Total time: ~10 minutes.

---

## Prerequisites

Install these before starting:

```bash
# macOS
brew install kind kubectl terraform helm

# Verify
kind version        # >= 0.22
kubectl version --client
terraform version   # >= 1.7
helm version
```

You also need:
- Docker running
- A GitHub account with a personal access token (`repo` scope)
- Python 3.11+

---

## Step 1 — Configure

```bash
git clone https://github.com/YOUR_USERNAME/gitops-platform.git
cd gitops-platform
cp .env.example .env
```

Edit `.env` and set at minimum:

```
GITHUB_TOKEN=ghp_...      # your real token
GITHUB_ORG=your-username  # or your org
GITHUB_TEMPLATE_REPO=your-username/app-template
```

> **Tip:** You need to create the template repo first. Push the contents of
> `gitops/apps/app-template/` to a new GitHub repo named `app-template` in your
> org. The platform will clone from it.

---

## Step 2 — Bootstrap the cluster

```bash
chmod +x scripts/*.sh
./scripts/setup-kind.sh
```

This takes ~3 minutes and prints:

```
ArgoCD admin password: <password>
Grafana admin password: admin
==> Cluster ready. Run: docker-compose up --build
```

Save the ArgoCD password — you'll need it later.

---

## Step 3 — Start the backend

```bash
docker-compose up --build
```

Wait until you see:
```
backend-1  | INFO:     Application startup complete.
```

---

## Step 4 — Provision an environment

Open `http://localhost:8081` in your browser.

Fill in:
- **Team name:** `platform`
- **App name:** `hello-world`
- **Description:** (optional)

Click **Provision**. In 30–60 seconds you'll see a checklist:

```
✓ GitHub repository: https://github.com/YOUR_ORG/platform-hello-world
✓ Kubernetes namespace: platform-hello-world
✓ ArgoCD application: platform-hello-world
✓ Grafana dashboard: http://localhost:3001/d/platform-hello-world/...
```

---

## Step 5 — Verify each resource

### GitHub

Open the GitHub URL from the provisioning result. You should see:
- Repo created from your template
- Branch protection on `main` (Settings → Branches)
- `CODEOWNERS` file in the root
- Topics: `platform`, `hello-world`, `idp`

### Kubernetes

```bash
# Namespace exists
kubectl get namespace platform-hello-world

# ResourceQuota is in place
kubectl describe resourcequota default-quota -n platform-hello-world

# ServiceAccount and RBAC
kubectl get serviceaccount,role,rolebinding -n platform-hello-world
```

### ArgoCD

```bash
kubectl port-forward svc/argocd-server -n argocd 8443:443
```

Open `https://localhost:8443` → login with `admin` / (password from step 2).
You should see the `platform-hello-world` Application syncing.

### Grafana

```bash
kubectl port-forward svc/monitoring-grafana -n monitoring 3001:80
```

Open `http://localhost:3001` → login with `admin` / `admin`.
Navigate to Dashboards → search for `platform-hello-world`.
You'll see three panels: Running Pods, CPU Usage, Memory Usage.

---

## Step 6 — Teardown a single environment

The API supports full teardown:

```bash
curl -X DELETE http://localhost:8000/provision/platform/hello-world
# Returns 204 No Content
```

This deletes in order:
1. ArgoCD Application + AppProject (cascade-deletes K8s workloads)
2. Terraform destroys namespace + RBAC
3. GitHub repo deleted
4. Grafana dashboard deleted

---

## Step 7 — Tear down the cluster

```bash
./scripts/teardown.sh
```

This deletes the kind cluster and removes local Terraform state files.
GitHub repos created during the demo must be deleted manually (or via the
teardown API before running this script).

---

## Running the tests (no cluster needed)

```bash
cd backend
pip install -r requirements.txt
python3 -m pytest tests/ -v
```

128 tests, all services mocked — runs in ~35 seconds on any machine.

```bash
# Helm chart validation
./scripts/helm-test.sh

# Terraform syntax + native tests (requires terraform >= 1.7)
./scripts/tf-test.sh
```

---

## Common issues

| Symptom | Fix |
|---|---|
| `docker-compose up` fails with kubeconfig error | Run `./scripts/setup-kind.sh` first |
| `kubectl` commands fail | `export KUBECONFIG=~/.kube/config` and verify `kubectl get nodes` works |
| ArgoCD Application stays `OutOfSync` | The template repo must be public, or add a deploy key |
| Grafana shows no data | Wait ~2 minutes for Prometheus to scrape the new namespace |
| `GITHUB_TOKEN` 401 error | Token needs the `repo` scope and must not be expired |
