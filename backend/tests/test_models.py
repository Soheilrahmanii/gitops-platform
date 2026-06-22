import pytest
from pydantic import ValidationError
from models.provision import ProvisionRequest, ProvisionResult


# ── resource_name ──────────────────────────────────────────────────────────────

def test_resource_name_combines_team_and_app():
    req = ProvisionRequest(team_name="platform", app_name="hello-world")
    assert req.resource_name == "platform-hello-world"


# ── valid slugs ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("team,app", [
    ("abc", "xyz"),         # minimum 3 chars each (regex: letter + 1-38 middle + trailing)
    ("my-team", "my-app"),
    ("a1b", "b2c"),         # letters+digits
    ("a" * 20, "b" * 19),  # near max length
])
def test_valid_slugs(team, app):
    req = ProvisionRequest(team_name=team, app_name=app)
    assert req.resource_name == f"{team}-{app}"


# ── invalid team_name ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", [
    "A",            # uppercase
    "1team",        # starts with digit
    "t",            # too short (1 char)
    "team name",    # space
    "team_name",    # underscore
    "-team",        # starts with hyphen
    "team-",        # ends with hyphen
    "a" * 41,       # too long
])
def test_invalid_team_name_raises(bad):
    with pytest.raises(ValidationError):
        ProvisionRequest(team_name=bad, app_name="valid-app")


@pytest.mark.parametrize("bad", [
    "HELLO",
    "2app",
    "app name",
    "app_name",
])
def test_invalid_app_name_raises(bad):
    with pytest.raises(ValidationError):
        ProvisionRequest(team_name="valid-team", app_name=bad)


# ── description ────────────────────────────────────────────────────────────────

def test_description_defaults_to_empty():
    req = ProvisionRequest(team_name="my-team", app_name="my-app")
    assert req.description == ""


def test_description_max_length_exceeded_raises():
    with pytest.raises(ValidationError):
        ProvisionRequest(team_name="my-team", app_name="my-app", description="x" * 257)


def test_description_at_max_length_is_valid():
    req = ProvisionRequest(team_name="my-team", app_name="my-app", description="x" * 256)
    assert len(req.description) == 256


# ── template_repo override ─────────────────────────────────────────────────────

def test_template_repo_is_optional():
    req = ProvisionRequest(team_name="my-team", app_name="my-app")
    assert req.template_repo is None


def test_template_repo_accepted():
    req = ProvisionRequest(team_name="my-team", app_name="my-app", template_repo="org/tpl")
    assert req.template_repo == "org/tpl"


# ── ProvisionResult ────────────────────────────────────────────────────────────

def test_provision_result_fields():
    result = ProvisionResult(
        status="success",
        github_repo="https://github.com/org/repo",
        namespace="my-team-my-app",
        argocd_app="my-team-my-app",
        grafana_dashboard="http://localhost:3000/d/my-team-my-app",
    )
    assert result.status == "success"
    assert "my-team-my-app" in result.namespace
