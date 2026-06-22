# Architecture & Design Decisions

## Why Terraform for namespace/RBAC instead of Helm or raw manifests?

Terraform tracks state. If you run `/provision` twice with the same name, Terraform
is idempotent without extra logic in the backend. It also makes it easy to add
more infrastructure (e.g. a Vault secret path, a Kafka topic) to the same apply.

Raw `kubectl apply` manifests would work for a toy demo but have no drift detection.

## Why `kubectl apply` for ArgoCD instead of the ArgoCD REST API?

The ArgoCD API requires an authentication token and the server address at runtime.
Using `kubectl apply` means the only credential needed is the kubeconfig — the same
one Terraform uses. It also means the manifest is a real GitOps artifact that could
later be committed to an "app of apps" repository.

## Why subprocess/shell-out instead of a Python Kubernetes SDK?

Two reasons:
1. The `kubernetes` Python client is ~20 MB of generated code. For a demo that
   shells out to `kubectl`, it adds complexity without value.
2. The shell commands are what a human would run, making the demo easier to
   narrate and debug live.

In a production platform you'd use the Python K8s client or a service mesh API.

## Why vanilla JS instead of React/Vue?

Recruiters and interviewers reading this code should focus on the platform logic,
not the frontend framework. Vanilla JS also removes the need for a build step,
so `docker-compose up` works without Node.js on the host.

## How to extend this for production

| Concern | Demo approach | Production approach |
|---|---|---|
| Secrets | `.env` file | Vault + dynamic secrets |
| Auth | None | OIDC/SSO on the form + backend |
| State | Local `.tfstate` | Terraform Cloud / S3 backend |
| GitOps repo | App repo itself | Separate GitOps repo, PR-based |
| Notifications | None | Slack webhook on provision success |
| Multi-tenancy | One kind cluster | Real K8s cluster per environment |
