from pathlib import Path
from unittest.mock import call, patch, MagicMock
import pytest
import yaml

from services.argocd import ArgoCDService

REAL_TEMPLATE_DIR = Path(__file__).parent.parent.parent / "gitops" / "argocd"

TEAM = "platform"
APP = "hello-world"
NAME = "platform-hello-world"
REPO = "https://github.com/test-org/platform-hello-world"


def _ok() -> MagicMock:
    m = MagicMock()
    m.returncode = 0
    return m


def _fail(stderr: str = "error") -> MagicMock:
    m = MagicMock()
    m.returncode = 1
    m.stderr = stderr
    return m


def _svc() -> ArgoCDService:
    return ArgoCDService(template_dir=REAL_TEMPLATE_DIR)


# ── AppProject template ────────────────────────────────────────────────────────

def test_project_manifest_is_valid_yaml():
    manifests = []
    svc = _svc()
    svc._kubectl = lambda action, m: manifests.append((action, m))
    svc._kubectl_delete = MagicMock()

    svc.create_application(TEAM, APP, REPO)

    project_manifest = manifests[0][1]
    doc = yaml.safe_load(project_manifest)
    assert doc["kind"] == "AppProject"


def test_project_name_matches_resource_name():
    manifests = []
    svc = _svc()
    svc._kubectl = lambda action, m: manifests.append((action, m))

    svc.create_application(TEAM, APP, REPO)

    doc = yaml.safe_load(manifests[0][1])
    assert doc["metadata"]["name"] == NAME


def test_project_destination_namespace_is_scoped():
    manifests = []
    svc = _svc()
    svc._kubectl = lambda action, m: manifests.append((action, m))

    svc.create_application(TEAM, APP, REPO)

    doc = yaml.safe_load(manifests[0][1])
    destinations = doc["spec"]["destinations"]
    assert len(destinations) == 1
    assert destinations[0]["namespace"] == NAME


def test_project_allows_no_cluster_resources():
    manifests = []
    svc = _svc()
    svc._kubectl = lambda action, m: manifests.append((action, m))

    svc.create_application(TEAM, APP, REPO)

    doc = yaml.safe_load(manifests[0][1])
    assert doc["spec"]["clusterResourceWhitelist"] == []


def test_project_team_label_is_set():
    manifests = []
    svc = _svc()
    svc._kubectl = lambda action, m: manifests.append((action, m))

    svc.create_application(TEAM, APP, REPO)

    doc = yaml.safe_load(manifests[0][1])
    assert doc["metadata"]["labels"]["team"] == TEAM


# ── Application template ───────────────────────────────────────────────────────

def test_application_manifest_is_valid_yaml():
    manifests = []
    svc = _svc()
    svc._kubectl = lambda action, m: manifests.append((action, m))

    svc.create_application(TEAM, APP, REPO)

    app_manifest = manifests[1][1]
    doc = yaml.safe_load(app_manifest)
    assert doc["kind"] == "Application"


def test_application_name_matches_resource_name():
    manifests = []
    svc = _svc()
    svc._kubectl = lambda action, m: manifests.append((action, m))

    svc.create_application(TEAM, APP, REPO)

    doc = yaml.safe_load(manifests[1][1])
    assert doc["metadata"]["name"] == NAME


def test_application_references_correct_project():
    manifests = []
    svc = _svc()
    svc._kubectl = lambda action, m: manifests.append((action, m))

    svc.create_application(TEAM, APP, REPO)

    doc = yaml.safe_load(manifests[1][1])
    assert doc["spec"]["project"] == NAME


def test_application_repo_url_is_set():
    manifests = []
    svc = _svc()
    svc._kubectl = lambda action, m: manifests.append((action, m))

    svc.create_application(TEAM, APP, REPO)

    doc = yaml.safe_load(manifests[1][1])
    assert doc["spec"]["source"]["repoURL"] == REPO


def test_application_destination_namespace_is_correct():
    manifests = []
    svc = _svc()
    svc._kubectl = lambda action, m: manifests.append((action, m))

    svc.create_application(TEAM, APP, REPO)

    doc = yaml.safe_load(manifests[1][1])
    assert doc["spec"]["destination"]["namespace"] == NAME


def test_application_has_automated_sync():
    manifests = []
    svc = _svc()
    svc._kubectl = lambda action, m: manifests.append((action, m))

    svc.create_application(TEAM, APP, REPO)

    doc = yaml.safe_load(manifests[1][1])
    assert doc["spec"]["syncPolicy"]["automated"]["prune"] is True
    assert doc["spec"]["syncPolicy"]["automated"]["selfHeal"] is True


def test_application_has_retry_policy():
    manifests = []
    svc = _svc()
    svc._kubectl = lambda action, m: manifests.append((action, m))

    svc.create_application(TEAM, APP, REPO)

    doc = yaml.safe_load(manifests[1][1])
    retry = doc["spec"]["syncPolicy"]["retry"]
    assert retry["limit"] >= 1
    assert "backoff" in retry


def test_application_has_ignore_differences_for_resource_limits():
    manifests = []
    svc = _svc()
    svc._kubectl = lambda action, m: manifests.append((action, m))

    svc.create_application(TEAM, APP, REPO)

    doc = yaml.safe_load(manifests[1][1])
    ignore = doc["spec"]["ignoreDifferences"]
    pointers = [p for entry in ignore for p in entry.get("jsonPointers", [])]
    assert any("resources" in p for p in pointers), (
        "ignoreDifferences must cover resource limits to prevent LimitRange drift"
    )


def test_application_namespace_create_is_disabled():
    manifests = []
    svc = _svc()
    svc._kubectl = lambda action, m: manifests.append((action, m))

    svc.create_application(TEAM, APP, REPO)

    doc = yaml.safe_load(manifests[1][1])
    options = doc["spec"]["syncPolicy"]["syncOptions"]
    assert "CreateNamespace=false" in options


def test_application_has_cascade_delete_finalizer():
    manifests = []
    svc = _svc()
    svc._kubectl = lambda action, m: manifests.append((action, m))

    svc.create_application(TEAM, APP, REPO)

    doc = yaml.safe_load(manifests[1][1])
    finalizers = doc["metadata"]["finalizers"]
    assert any("resources-finalizer" in f for f in finalizers)


# ── apply order ────────────────────────────────────────────────────────────────

def test_project_is_applied_before_application():
    """AppProject must exist before the Application that references it."""
    actions = []
    manifests = []
    svc = _svc()
    svc._kubectl = lambda action, m: (actions.append(action), manifests.append(m))

    svc.create_application(TEAM, APP, REPO)

    kinds = [yaml.safe_load(m)["kind"] for m in manifests]
    assert kinds == ["AppProject", "Application"]


def test_kubectl_is_called_with_apply():
    actions = []
    svc = _svc()
    svc._kubectl = lambda action, m: actions.append(action)

    svc.create_application(TEAM, APP, REPO)

    assert all(a == "apply" for a in actions)


# ── kubectl error handling ─────────────────────────────────────────────────────

def test_kubectl_failure_raises_runtime_error():
    with patch("subprocess.run", return_value=_fail("connection refused")):
        with pytest.raises(RuntimeError, match="connection refused"):
            _svc().create_application(TEAM, APP, REPO)


# ── delete_application ─────────────────────────────────────────────────────────

def test_delete_application_calls_kubectl_delete_for_application():
    with patch("subprocess.run", return_value=_ok()) as mock_run:
        _svc().delete_application(TEAM, APP)

    cmds = [c.args[0] for c in mock_run.call_args_list]
    assert any("application" in cmd and NAME in cmd for cmd in cmds)


def test_delete_application_calls_kubectl_delete_for_project():
    with patch("subprocess.run", return_value=_ok()) as mock_run:
        _svc().delete_application(TEAM, APP)

    cmds = [c.args[0] for c in mock_run.call_args_list]
    assert any("appproject" in cmd and NAME in cmd for cmd in cmds)


def test_delete_application_deletes_app_before_project():
    """Application finalizer runs first; project must not disappear underneath it."""
    deleted_kinds = []

    def fake_run(cmd, **kwargs):
        for kind in ("application", "appproject"):
            if kind in cmd:
                deleted_kinds.append(kind)
        return _ok()

    with patch("subprocess.run", side_effect=fake_run):
        _svc().delete_application(TEAM, APP)

    assert deleted_kinds == ["application", "appproject"]


def test_delete_uses_ignore_not_found_flag():
    with patch("subprocess.run", return_value=_ok()) as mock_run:
        _svc().delete_application(TEAM, APP)

    for c in mock_run.call_args_list:
        assert "--ignore-not-found" in c.args[0]
