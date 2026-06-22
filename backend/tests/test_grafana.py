import json
import pytest
import httpx

from services.grafana import GrafanaService

NS = "platform-hello-world"

_CREATE_OK = {
    "id": 1,
    "uid": NS,
    "url": f"/d/{NS}/idp-platform-hello-world",
    "status": "success",
    "version": 1,
}


def _svc(status: int = 200, body: dict | None = None) -> GrafanaService:
    _body = body or {}

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=_body)

    return GrafanaService(transport=httpx.MockTransport(handler))


def _routing_svc(*routes) -> GrafanaService:
    """Build a GrafanaService whose transport dispatches by (method, URL fragment)."""
    def handler(req: httpx.Request) -> httpx.Response:
        for method, fragment, status, body in routes:
            if req.method == method and fragment in str(req.url):
                return httpx.Response(status, json=body)
        return httpx.Response(200, json={})

    return GrafanaService(transport=httpx.MockTransport(handler))


# ── create_dashboard ───────────────────────────────────────────────────────────

async def test_create_dashboard_returns_full_url():
    svc = _svc(200, _CREATE_OK)
    url = await svc.create_dashboard(NS)
    assert url == f"http://grafana-test:3000/d/{NS}/idp-platform-hello-world"


async def test_create_dashboard_posts_to_dashboards_db():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        captured["method"] = req.method
        return httpx.Response(200, json=_CREATE_OK)

    await GrafanaService(transport=httpx.MockTransport(handler)).create_dashboard(NS)

    assert captured["method"] == "POST"
    assert "api/dashboards/db" in captured["url"]


async def test_create_dashboard_sets_overwrite_true():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.read())
        return httpx.Response(200, json=_CREATE_OK)

    await GrafanaService(transport=httpx.MockTransport(handler)).create_dashboard(NS)

    assert captured["body"]["overwrite"] is True


async def test_create_dashboard_uid_matches_namespace():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.read())
        return httpx.Response(200, json=_CREATE_OK)

    await GrafanaService(transport=httpx.MockTransport(handler)).create_dashboard(NS)

    assert captured["body"]["dashboard"]["uid"] == NS


async def test_create_dashboard_title_contains_namespace():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.read())
        return httpx.Response(200, json=_CREATE_OK)

    await GrafanaService(transport=httpx.MockTransport(handler)).create_dashboard(NS)

    assert NS in captured["body"]["dashboard"]["title"]


async def test_create_dashboard_has_three_panels():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.read())
        return httpx.Response(200, json=_CREATE_OK)

    await GrafanaService(transport=httpx.MockTransport(handler)).create_dashboard(NS)

    panels = captured["body"]["dashboard"]["panels"]
    assert len(panels) == 3


async def test_create_dashboard_panel_types():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.read())
        return httpx.Response(200, json=_CREATE_OK)

    await GrafanaService(transport=httpx.MockTransport(handler)).create_dashboard(NS)

    types = {p["type"] for p in captured["body"]["dashboard"]["panels"]}
    assert "stat" in types
    assert "timeseries" in types


async def test_create_dashboard_prometheus_queries_scoped_to_namespace():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.read())
        return httpx.Response(200, json=_CREATE_OK)

    await GrafanaService(transport=httpx.MockTransport(handler)).create_dashboard(NS)

    all_exprs = [
        t["expr"]
        for panel in captured["body"]["dashboard"]["panels"]
        for t in panel.get("targets", [])
    ]
    assert all(NS in expr for expr in all_exprs), (
        "All PromQL expressions must be scoped to the namespace"
    )


async def test_create_dashboard_tags_include_namespace_and_idp():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.read())
        return httpx.Response(200, json=_CREATE_OK)

    await GrafanaService(transport=httpx.MockTransport(handler)).create_dashboard(NS)

    tags = captured["body"]["dashboard"]["tags"]
    assert "gitops-platform" in tags
    assert NS in tags


async def test_create_dashboard_uses_basic_auth():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["auth"] = req.headers.get("authorization", "")
        return httpx.Response(200, json=_CREATE_OK)

    await GrafanaService(transport=httpx.MockTransport(handler)).create_dashboard(NS)

    assert captured["auth"].startswith("Basic ")


async def test_create_dashboard_raises_on_http_error():
    with pytest.raises(httpx.HTTPStatusError):
        await _svc(500, {"message": "Internal Server Error"}).create_dashboard(NS)


# ── delete_dashboard ───────────────────────────────────────────────────────────

async def test_delete_dashboard_calls_correct_endpoint():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["method"] = req.method
        captured["url"] = str(req.url)
        return httpx.Response(200, json={"message": "Dashboard deleted"})

    await GrafanaService(transport=httpx.MockTransport(handler)).delete_dashboard(NS)

    assert captured["method"] == "DELETE"
    assert f"dashboards/uid/{NS}" in captured["url"]


async def test_delete_dashboard_is_idempotent_on_404():
    svc = _svc(404, {"message": "Not found"})
    await svc.delete_dashboard(NS)  # must not raise


async def test_delete_dashboard_raises_on_unexpected_error():
    with pytest.raises(httpx.HTTPStatusError):
        await _svc(500, {}).delete_dashboard(NS)


# ── _build_dashboard internals ─────────────────────────────────────────────────

def test_build_dashboard_uid_is_truncated_to_40_chars():
    svc = GrafanaService()
    long_ns = "a" * 50
    dashboard = svc._build_dashboard(long_ns)
    assert len(dashboard["uid"]) <= 40


def test_build_dashboard_refresh_is_set():
    svc = GrafanaService()
    dashboard = svc._build_dashboard(NS)
    assert dashboard.get("refresh")


def test_build_dashboard_memory_panel_has_bytes_unit():
    svc = GrafanaService()
    dashboard = svc._build_dashboard(NS)
    mem_panel = next(p for p in dashboard["panels"] if "Memory" in p["title"])
    unit = mem_panel.get("fieldConfig", {}).get("defaults", {}).get("unit")
    assert unit == "bytes"
