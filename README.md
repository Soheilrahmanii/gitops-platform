# GitOps Platform

A minimal but realistic self-service platform that provisions a full developer
environment from a single form submission.

> **Portfolio note:** This project demonstrates platform engineering skills:
> GitOps, infrastructure-as-code, Kubernetes RBAC, API design, and self-service
> automation — all wired together in a locally runnable demo.

---

## What It Does

A developer fills out a form with a team name and app name. Within seconds they get:

| Resource | Tool | What's created |
|---|---|---|
| GitHub repo | GitHub API | Repo from template, with branch protection |
| K8s namespace | Terraform + kind | Namespace with ResourceQuota and LimitRange |
| RBAC | Terraform | Role + RoleBinding scoped to the namespace |
| GitOps app | ArgoCD | `Application` CR pointing at the new repo |
| Dashboard | Grafana | Pre-built dashboard for the namespace |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Developer                            │
│                    (browser form)                           │
└────────────────────────┬────────────────────────────────────┘
                         │  POST /provision
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Backend                           │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  GitHub     │  │  Terraform   │  │  ArgoCD          │  │
│  │  Service    │  │  Service     │  │  Service         │  │
│  │             │  │              │  │                  │  │
│  │ create repo │  │ namespace +  │  │ apply            │  │
│  │ from tpl    │  │ rbac         │  │ Application CR   │  │
│  └─────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                  │                    │
         ▼                  ▼                    ▼
   github.com        kind cluster          ArgoCD API
   (new repo)     (new namespace)      (new Application)
                                              │
                                             GitOps sync
                                              │
                                        Grafana dashboard
```

---

## Project Layout

```
.
├── backend/                    # FastAPI application
│   ├── main.py                 # App entrypoint, CORS, lifespan
│   ├── routers/
│   │   └── provision.py        # POST /provision endpoint
│   ├── services/
│   │   ├── github.py           # GitHub repo creation
│   │   ├── terraform.py        # Runs terraform apply via subprocess
│   │   └── argocd.py           # Creates ArgoCD Application CR
│   └── models/
│       └── provision.py        # Pydantic request/response models
│
├── terraform/                  # Infrastructure as code
│   ├── main.tf                 # Root module — wires namespace + rbac
│   ├── variables.tf
│   ├── outputs.tf
│   └── modules/
│       ├── namespace/          # K8s Namespace + ResourceQuota
│       └── rbac/               # Role + RoleBinding
│
├── gitops/
│   ├── apps/
│   │   └── app-template/       # Helm chart used as the app template
│   │       ├── Chart.yaml
│   │       ├── values.yaml
│   │       └── templates/
│   │           ├── deployment.yaml
│   │           └── service.yaml
│   └── argocd/
│       └── application-template.yaml   # Jinja2 template for ArgoCD CR
│
├── frontend/
│   ├── index.html              # Provision form
│   ├── style.css
│   └── app.js                  # Calls POST /provision, renders result
│
├── scripts/
│   ├── setup-kind.sh           # Bootstraps kind + ArgoCD + Grafana
│   ├── helm-test.sh            # Validates the Helm chart
│   ├── tf-test.sh              # Runs Terraform tests
│   └── teardown.sh             # Destroys everything cleanly
│
├── docs/
│   ├── architecture.md         # Detailed design decisions
│   └── demo-guide.md           # Step-by-step walkthrough for demos
│
├── docker-compose.yml          # Runs backend + frontend locally
└── .env.example                # Required environment variables
```

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Docker | ≥ 24 | Containers |
| kind | ≥ 0.22 | Local K8s cluster |
| kubectl | ≥ 1.28 | K8s CLI |
| Terraform | ≥ 1.7 | Infra provisioning |
| Helm | ≥ 3.14 | Chart rendering |
| Python | ≥ 3.11 | Backend runtime |
| GitHub token | — | Repo creation (needs `repo` and `delete_repo` scopes) |

---

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/YOUR_USERNAME/gitops-platform.git
cd gitops-platform
cp .env.example .env
# Edit .env — at minimum set GITHUB_TOKEN and GITHUB_ORG
```

### 2. Bootstrap the cluster

```bash
chmod +x scripts/*.sh
./scripts/setup-kind.sh
```

This creates a `kind` cluster named `gitops-platform`, installs ArgoCD, and sets up
Grafana. Takes ~3 minutes.

### 3. Start the backend

```bash
docker compose up --build
```

The API is at `http://localhost:8000` and the form is at `http://localhost:8081`.

### 4. Provision an environment

Open `http://localhost:8081`, fill in:
- **Team name:** `platform`
- **App name:** `hello-world`

Click **Provision**. In ~30 seconds you'll have a GitHub repo, Kubernetes
namespace, ArgoCD application, and Grafana dashboard.

### 5. Verify

```bash
# See the new namespace
kubectl get namespace platform-hello-world

# See RBAC
kubectl get rolebinding -n platform-hello-world

# Open ArgoCD UI (password in .env or from the setup script output)
kubectl port-forward svc/argocd-server -n argocd 8443:443
# → https://localhost:8443

# Open Grafana (started automatically by setup-kind.sh, but re-run if needed)
kubectl port-forward svc/monitoring-grafana -n monitoring 3001:80
# → http://localhost:3001
```

---

## API Reference

### `POST /provision`

Creates a full developer environment.

**Request body:**
```json
{
  "team_name": "platform",
  "app_name": "hello-world",
  "description": "Optional app description",
  "template_repo": "YOUR_ORG/app-template"   // optional override
}
```

**Response:**
```json
{
  "status": "success",
  "github_repo": "https://github.com/YOUR_ORG/platform-hello-world",
  "namespace": "platform-hello-world",
  "argocd_app": "platform-hello-world",
  "grafana_dashboard": "http://localhost:3001/d/platform-hello-world"
}
```

### `GET /health`

Returns `{"status": "ok"}`. Used by Docker health checks.

---

## Component Breakdown

### Backend (`backend/`)

FastAPI app with three service classes, each independently testable:

- **`GitHubService`** — wraps the GitHub REST API to create a repo from a
  template, set branch protection, and add a `CODEOWNERS` file.
- **`TerraformService`** — writes a `.tfvars` file and shells out to
  `terraform apply`. Uses the local kubeconfig from the kind cluster.
- **`ArgoCDService`** — renders `application-template.yaml` with Jinja2 and
  applies it with `kubectl`. No ArgoCD SDK dependency.

### Terraform (`terraform/`)

Two reusable modules:

- **`namespace`** — creates a `Namespace` with `ResourceQuota` (CPU/memory
  limits) and `LimitRange` (default container limits).
- **`rbac`** — creates a `Role` with standard dev permissions and a
  `RoleBinding` that grants it to a `ServiceAccount` named after the team.

### GitOps (`gitops/`)

- **`app-template/`** — a minimal Helm chart used as the GitHub repo template.
  New repos are copies of this chart, ready for ArgoCD to sync.
- **`application-template.yaml`** — Jinja2 template that becomes an ArgoCD
  `Application` CR, pointing `targetRevision: HEAD` at the new repo.

### Frontend (`frontend/`)

Plain HTML + vanilla JS. No build step, no framework. The form posts JSON to
the backend and renders the result as a checklist of created resources. Kept
simple intentionally — the platform logic is what matters.

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|---|---|---|
| `GITHUB_TOKEN` | Yes | Personal access token with `repo` and `delete_repo` scopes |
| `GITHUB_ORG` | Yes | GitHub org or username to create repos under |
| `GITHUB_TEMPLATE_REPO` | Yes | `org/repo` of the template repo |
| `GRAFANA_URL` | No | Grafana URL (default: `http://localhost:3001`) |
| `GRAFANA_USER` | No | Grafana username (default: `admin`) |
| `GRAFANA_PASSWORD` | No | Grafana password (default: `admin`) |

---

## Running Tests

```bash
# Backend unit tests (no cluster needed)
cd backend
pip install -r requirements.txt
pytest tests/ -v

# End-to-end: start the stack first, then provision via the UI
./scripts/setup-kind.sh
docker compose up --build
```

---

## Teardown

```bash
./scripts/teardown.sh
```

Deletes the kind cluster, removes locally created `.tfstate` files, and
optionally deletes the GitHub repos created during testing.

---

## Design Decisions

See [`docs/architecture.md`](docs/architecture.md) for detailed reasoning on:

- Why Terraform over Helm for namespace/RBAC (state management)
- Why `kubectl apply` over ArgoCD SDK (fewer dependencies)
- Why vanilla JS over React (demo clarity)
- How to extend this for production (Vault, SSO, real GitOps repo)

---

## Roadmap

- [ ] Vault integration for secret injection
- [ ] Slack/Teams notification on provision complete
- [x] Self-service teardown endpoint (`DELETE /provision/{team_name}/{app_name}`)
- [ ] Backstage plugin wrapper
- [ ] GitHub Actions workflow in provisioned repos

---

## License

MIT
