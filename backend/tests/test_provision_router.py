"""
Router-level tests: exercises POST /provision and DELETE /provision/{team}/{app}
end-to-end through FastAPI, with all four services mocked.
"""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import AsyncClient, ASGITransport

from main import app

VALID_PAYLOAD = {
    "team_name": "platform",
    "app_name": "hello-world",
    "description": "Test app",
}

MOCK_REPO_URL = "https://github.com/test-org/platform-hello-world"
MOCK_DASHBOARD_URL = "http://grafana-test:3000/d/platform-hello-world/idp-platform-hello-world"


def _patch_services(
    repo_url: str = MOCK_REPO_URL,
    dashboard_url: str = MOCK_DASHBOARD_URL,
    github_raises=None,
    tf_raises=None,
    argocd_raises=None,
    grafana_raises=None,
):
    """Returns context managers that patch all four service classes."""
    github_mock = MagicMock()
    github_mock.return_value.provision_repo = AsyncMock(
        return_value=repo_url, side_effect=github_raises
    )
    github_mock.return_value.delete_repo = AsyncMock()

    tf_mock = MagicMock()
    tf_mock.return_value.apply = MagicMock(side_effect=tf_raises)
    tf_mock.return_value.destroy = MagicMock()

    argocd_mock = MagicMock()
    argocd_mock.return_value.create_application = MagicMock(side_effect=argocd_raises)
    argocd_mock.return_value.delete_application = MagicMock()

    grafana_mock = MagicMock()
    grafana_mock.return_value.create_dashboard = AsyncMock(
        return_value=dashboard_url, side_effect=grafana_raises
    )
    grafana_mock.return_value.delete_dashboard = AsyncMock()

    return (
        patch("routers.provision.GitHubService", github_mock),
        patch("routers.provision.TerraformService", tf_mock),
        patch("routers.provision.ArgoCDService", argocd_mock),
        patch("routers.provision.GrafanaService", grafana_mock),
        github_mock, tf_mock, argocd_mock, grafana_mock,
    )


# ── health ─────────────────────────────────────────────────────────────────────

async def test_health_returns_ok():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ── POST /provision — happy path ───────────────────────────────────────────────

async def test_provision_returns_201():
    p_gh, p_tf, p_argocd, p_gf, *_ = _patch_services()
    with p_gh, p_tf, p_argocd, p_gf:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/provision", json=VALID_PAYLOAD)
    assert resp.status_code == 201


async def test_provision_response_contains_github_repo():
    p_gh, p_tf, p_argocd, p_gf, *_ = _patch_services()
    with p_gh, p_tf, p_argocd, p_gf:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/provision", json=VALID_PAYLOAD)
    assert resp.json()["github_repo"] == MOCK_REPO_URL


async def test_provision_response_contains_namespace():
    p_gh, p_tf, p_argocd, p_gf, *_ = _patch_services()
    with p_gh, p_tf, p_argocd, p_gf:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/provision", json=VALID_PAYLOAD)
    assert resp.json()["namespace"] == "platform-hello-world"


async def test_provision_response_contains_grafana_url():
    p_gh, p_tf, p_argocd, p_gf, *_ = _patch_services()
    with p_gh, p_tf, p_argocd, p_gf:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/provision", json=VALID_PAYLOAD)
    assert resp.json()["grafana_dashboard"] == MOCK_DASHBOARD_URL


async def test_provision_calls_all_four_services():
    p_gh, p_tf, p_argocd, p_gf, gh, tf, argocd, gf = _patch_services()
    with p_gh, p_tf, p_argocd, p_gf:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await c.post("/provision", json=VALID_PAYLOAD)

    gh.return_value.provision_repo.assert_called_once()
    tf.return_value.apply.assert_called_once_with("platform", "hello-world")
    argocd.return_value.create_application.assert_called_once_with(
        "platform", "hello-world", MOCK_REPO_URL
    )
    gf.return_value.create_dashboard.assert_called_once_with("platform-hello-world")


async def test_provision_passes_repo_url_to_argocd():
    custom_url = "https://github.com/test-org/custom-url"
    p_gh, p_tf, p_argocd, p_gf, _, _, argocd, _ = _patch_services(repo_url=custom_url)
    with p_gh, p_tf, p_argocd, p_gf:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await c.post("/provision", json=VALID_PAYLOAD)
    argocd.return_value.create_application.assert_called_once_with(
        "platform", "hello-world", custom_url
    )


# ── POST /provision — input validation ────────────────────────────────────────

async def test_invalid_team_name_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/provision", json={**VALID_PAYLOAD, "team_name": "UPPER"})
    assert resp.status_code == 422


async def test_invalid_app_name_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/provision", json={**VALID_PAYLOAD, "app_name": "has space"})
    assert resp.status_code == 422


async def test_missing_required_fields_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/provision", json={"team_name": "platform"})
    assert resp.status_code == 422


# ── POST /provision — service errors ──────────────────────────────────────────

async def test_github_error_returns_500():
    p_gh, p_tf, p_argocd, p_gf, *_ = _patch_services(
        github_raises=RuntimeError("rate limited")
    )
    with p_gh, p_tf, p_argocd, p_gf:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/provision", json=VALID_PAYLOAD)
    assert resp.status_code == 500
    assert "rate limited" in resp.json()["detail"]


async def test_terraform_error_returns_500():
    p_gh, p_tf, p_argocd, p_gf, *_ = _patch_services(
        tf_raises=RuntimeError("provider not found")
    )
    with p_gh, p_tf, p_argocd, p_gf:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/provision", json=VALID_PAYLOAD)
    assert resp.status_code == 500


async def test_grafana_error_returns_500():
    p_gh, p_tf, p_argocd, p_gf, *_ = _patch_services(
        grafana_raises=RuntimeError("grafana unreachable")
    )
    with p_gh, p_tf, p_argocd, p_gf:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/provision", json=VALID_PAYLOAD)
    assert resp.status_code == 500
    assert "grafana unreachable" in resp.json()["detail"]


# ── DELETE /provision/{team}/{app} — happy path ───────────────────────────────

async def test_deprovision_returns_204():
    p_gh, p_tf, p_argocd, p_gf, *_ = _patch_services()
    with p_gh, p_tf, p_argocd, p_gf:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.delete("/provision/platform/hello-world")
    assert resp.status_code == 204


async def test_deprovision_calls_all_four_services():
    p_gh, p_tf, p_argocd, p_gf, gh, tf, argocd, gf = _patch_services()
    with p_gh, p_tf, p_argocd, p_gf:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await c.delete("/provision/platform/hello-world")

    argocd.return_value.delete_application.assert_called_once_with("platform", "hello-world")
    tf.return_value.destroy.assert_called_once_with("platform", "hello-world")
    gh.return_value.delete_repo.assert_called_once_with("platform-hello-world")
    gf.return_value.delete_dashboard.assert_called_once_with("platform-hello-world")


async def test_deprovision_argocd_called_before_terraform():
    """ArgoCD cascade finalizer must run before Terraform destroys the namespace."""
    call_order = []
    p_gh, p_tf, p_argocd, p_gf, gh, tf, argocd, gf = _patch_services()

    argocd.return_value.delete_application.side_effect = lambda *a, **kw: call_order.append("argocd")
    tf.return_value.destroy.side_effect = lambda *a, **kw: call_order.append("terraform")

    with p_gh, p_tf, p_argocd, p_gf:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await c.delete("/provision/platform/hello-world")

    assert call_order == ["argocd", "terraform"]


# ── DELETE /provision — input validation ──────────────────────────────────────

async def test_deprovision_invalid_team_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.delete("/provision/UPPER/hello-world")
    assert resp.status_code == 422


async def test_deprovision_invalid_app_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.delete("/provision/platform/has_underscore")
    assert resp.status_code == 422


# ── DELETE /provision — service errors ────────────────────────────────────────

async def test_deprovision_service_error_returns_500():
    p_gh, p_tf, p_argocd, p_gf, _, _, argocd, _ = _patch_services()
    argocd.return_value.delete_application.side_effect = RuntimeError("cluster unreachable")
    with p_gh, p_tf, p_argocd, p_gf:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.delete("/provision/platform/hello-world")
    assert resp.status_code == 500
    assert "cluster unreachable" in resp.json()["detail"]
