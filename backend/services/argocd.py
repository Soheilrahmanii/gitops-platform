"""
ArgoCDService — renders ArgoCD manifests and applies/deletes them.

We use kubectl apply/delete rather than the ArgoCD REST API because:
- kubectl works regardless of ArgoCD version.
- The rendered manifests are real GitOps artifacts (committable to a repo later).
- No additional credential management for an ArgoCD API token.
"""
import os
import subprocess
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# Resolves to /app/gitops/argocd inside the container (docker-compose mounts ./gitops:/app/gitops).
_TEMPLATE_DIR = Path(__file__).parent.parent / "gitops" / "argocd"


class ArgoCDService:
    def __init__(self, template_dir: Path = _TEMPLATE_DIR) -> None:
        self._jinja = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=False,   # YAML doesn't need HTML escaping
            keep_trailing_newline=True,
        )
        self._github_org = os.environ.get("GITHUB_ORG", "")

    def create_application(self, team_name: str, app_name: str, repo_url: str) -> None:
        """Creates an AppProject then an Application, in that order.

        The Application references the project by name, so the project must
        exist first or ArgoCD will reject the Application on sync.
        """
        name = f"{team_name}-{app_name}"
        ctx = self._render_context(team_name, app_name, repo_url)

        project_manifest = self._render("appproject-template.yaml", ctx)
        app_manifest = self._render("application-template.yaml", ctx)

        # Apply project first — Application references it.
        self._kubectl("apply", project_manifest)
        self._kubectl("apply", app_manifest)

    def delete_application(self, team_name: str, app_name: str) -> None:
        """Deletes the Application and AppProject.

        Deletes Application first so ArgoCD's finalizer has time to remove
        child resources before the project disappears.
        """
        name = f"{team_name}-{app_name}"
        self._kubectl_delete("application", name)
        self._kubectl_delete("appproject", name)

    # ── private helpers ────────────────────────────────────────────────────────

    def _render_context(self, team_name: str, app_name: str, repo_url: str) -> dict:
        name = f"{team_name}-{app_name}"
        return {
            "app_name": name,
            "team_name": team_name,
            "project_name": name,
            "repo_url": repo_url,
            "namespace": name,
            "target_revision": "HEAD",
            "github_org_url": f"https://github.com/{self._github_org}",
        }

    def _render(self, template_name: str, context: dict) -> str:
        return self._jinja.get_template(template_name).render(**context)

    def _kubectl(self, action: str, manifest: str) -> None:
        result = subprocess.run(
            ["kubectl", action, "-f", "-", "--validate=false",
             "--kubeconfig", "/root/.kube/config"],
            input=manifest,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"kubectl {action} failed:\n{result.stderr}"
            )

    def _kubectl_delete(self, kind: str, name: str) -> None:
        result = subprocess.run(
            ["kubectl", "delete", kind, name, "-n", "argocd",
             "--ignore-not-found", "--kubeconfig", "/root/.kube/config"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"kubectl delete {kind}/{name} failed:\n{result.stderr}"
            )
