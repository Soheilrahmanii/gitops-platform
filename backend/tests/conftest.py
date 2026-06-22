"""
Shared fixtures used across all test modules.
"""
import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    """Inject dummy service env vars so no test needs real credentials."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_ORG", "test-org")
    monkeypatch.setenv("GITHUB_TEMPLATE_REPO", "test-org/app-template")
    monkeypatch.setenv("GRAFANA_URL", "http://grafana-test:3000")
    monkeypatch.setenv("GRAFANA_USER", "admin")
    monkeypatch.setenv("GRAFANA_PASSWORD", "admin")
