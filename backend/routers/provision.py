"""
POST /provision   — provisions a full developer environment.
DELETE /provision/{team_name}/{app_name} — tears it all down.

Both endpoints run their service calls sequentially: each step depends on or
affects the previous one, and sequential ordering makes failures easy to reason
about in a demo context.
"""
import logging
from fastapi import APIRouter, HTTPException, Path

from models.provision import ProvisionRequest, ProvisionResult
from services.github import GitHubService
from services.terraform import TerraformService
from services.argocd import ArgoCDService
from services.grafana import GrafanaService

logger = logging.getLogger(__name__)
router = APIRouter()

_SLUG = r"^[a-z][a-z0-9-]{1,38}[a-z0-9]$"


@router.post("/provision", response_model=ProvisionResult, status_code=201)
async def provision(req: ProvisionRequest) -> ProvisionResult:
    name = req.resource_name
    logger.info("Starting provision for %s", name)

    try:
        repo_url = await GitHubService().provision_repo(req)
        logger.info("GitHub repo provisioned: %s", repo_url)

        TerraformService().apply(req.team_name, req.app_name)
        logger.info("Namespace + RBAC applied: %s", name)

        ArgoCDService().create_application(req.team_name, req.app_name, repo_url)
        logger.info("ArgoCD Application created: %s", name)

        dashboard_url = await GrafanaService().create_dashboard(name)
        logger.info("Grafana dashboard created: %s", dashboard_url)

    except Exception as exc:
        logger.exception("Provision failed for %s", name)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ProvisionResult(
        status="success",
        github_repo=repo_url,
        namespace=name,
        argocd_app=name,
        grafana_dashboard=dashboard_url,
    )


@router.delete("/provision/{team_name}/{app_name}", status_code=204)
async def deprovision(
    team_name: str = Path(pattern=_SLUG),
    app_name: str = Path(pattern=_SLUG),
) -> None:
    name = f"{team_name}-{app_name}"
    logger.info("Starting deprovision for %s", name)

    try:
        # ArgoCD first: its cascade finalizer removes the K8s workloads cleanly.
        ArgoCDService().delete_application(team_name, app_name)
        logger.info("ArgoCD Application deleted: %s", name)

        # Terraform second: destroys the now-empty namespace and RBAC.
        TerraformService().destroy(team_name, app_name)
        logger.info("Namespace + RBAC destroyed: %s", name)

        await GitHubService().delete_repo(name)
        logger.info("GitHub repo deleted: %s", name)

        await GrafanaService().delete_dashboard(name)
        logger.info("Grafana dashboard deleted: %s", name)

    except Exception as exc:
        logger.exception("Deprovision failed for %s", name)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
