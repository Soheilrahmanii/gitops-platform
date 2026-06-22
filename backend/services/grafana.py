"""
GrafanaService — provisions and deletes per-namespace Grafana dashboards.

Uses the Grafana HTTP API (basic auth) rather than provisioning files on disk
because the API works regardless of how Grafana is deployed (docker-compose,
Helm chart, cloud-managed) and the dashboard is immediately visible without
a pod restart.
"""
import os
from contextlib import asynccontextmanager

import httpx

_DEFAULT_URL = "http://localhost:3001"


class GrafanaService:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._url = os.environ.get("GRAFANA_URL", _DEFAULT_URL).rstrip("/")
        self._user = os.environ.get("GRAFANA_USER", "admin")
        self._password = os.environ.get("GRAFANA_PASSWORD", "admin")
        self._transport = transport

    # ── public API ─────────────────────────────────────────────────────────────

    async def create_dashboard(self, namespace: str) -> str:
        """Creates (or overwrites) a namespace dashboard and returns its URL."""
        payload = {
            "dashboard": self._build_dashboard(namespace),
            "overwrite": True,
            "folderId": 0,
        }
        async with self._client() as client:
            resp = await client.post(f"{self._url}/api/dashboards/db", json=payload)
            resp.raise_for_status()
            # Grafana returns the relative URL: /d/{uid}/{slug}
            return f"{self._url}{resp.json()['url']}"

    async def delete_dashboard(self, namespace: str) -> None:
        """Deletes the dashboard by UID. 404 is silently ignored (idempotent)."""
        async with self._client() as client:
            resp = await client.delete(
                f"{self._url}/api/dashboards/uid/{namespace}"
            )
            if resp.status_code not in (200, 404):
                resp.raise_for_status()

    # ── private helpers ────────────────────────────────────────────────────────

    def _build_dashboard(self, namespace: str) -> dict:
        """Returns a Grafana dashboard dict with three panels scoped to the namespace.

        Panel layout:
          [0,0] Running Pods (stat)     — quick health-check number
          [0,4] CPU Usage (timeseries)  — per-pod CPU cores
          [12,4] Memory Usage (timeseries) — per-pod bytes
        """
        # PromQL expressions scoped to this namespace.
        q_pods = f'count(kube_pod_info{{namespace="{namespace}"}})'
        q_cpu  = f'sum by (pod)(rate(container_cpu_usage_seconds_total{{namespace="{namespace}",container!=""}}[5m]))'
        q_mem  = f'sum by (pod)(container_memory_working_set_bytes{{namespace="{namespace}",container!=""}})'

        prom_ds = {"type": "prometheus", "uid": "prometheus"}

        def target(expr: str) -> dict:
            return {"expr": expr, "legendFormat": "{{pod}}", "refId": "A", "datasource": prom_ds}

        return {
            "uid": namespace[:40],   # Grafana UID max 40 chars
            "title": f"IDP — {namespace}",
            "tags": ["gitops-platform", namespace],
            "timezone": "browser",
            "schemaVersion": 38,
            "refresh": "30s",
            "panels": [
                {
                    "id": 1,
                    "type": "stat",
                    "title": "Running Pods",
                    "gridPos": {"h": 4, "w": 6, "x": 0, "y": 0},
                    "datasource": prom_ds,
                    "targets": [target(q_pods)],
                    "options": {"reduceOptions": {"calcs": ["lastNotNull"]}},
                },
                {
                    "id": 2,
                    "type": "timeseries",
                    "title": "CPU Usage (cores)",
                    "gridPos": {"h": 8, "w": 12, "x": 0, "y": 4},
                    "datasource": prom_ds,
                    "targets": [target(q_cpu)],
                },
                {
                    "id": 3,
                    "type": "timeseries",
                    "title": "Memory Usage",
                    "gridPos": {"h": 8, "w": 12, "x": 12, "y": 4},
                    "datasource": prom_ds,
                    "targets": [target(q_mem)],
                    "fieldConfig": {"defaults": {"unit": "bytes"}},
                },
            ],
        }

    @asynccontextmanager
    async def _client(self):
        async with httpx.AsyncClient(
            auth=(self._user, self._password),
            timeout=10,
            transport=self._transport,
        ) as client:
            yield client
