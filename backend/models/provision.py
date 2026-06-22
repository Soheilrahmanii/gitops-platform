"""
Pydantic models for the /provision endpoint.

Keeping models in their own module lets each service import only what it needs
and makes the shape of the API contract obvious at a glance.
"""
from pydantic import BaseModel, Field, field_validator
import re


_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,38}[a-z0-9]$")


def _validate_slug(value: str, field_name: str) -> str:
    if not _SLUG_RE.match(value):
        raise ValueError(
            f"{field_name} must be lowercase alphanumeric with hyphens, "
            "3–40 chars, starting with a letter."
        )
    return value


class ProvisionRequest(BaseModel):
    team_name: str = Field(..., examples=["platform"])
    app_name: str = Field(..., examples=["hello-world"])
    description: str = Field(default="", max_length=256)
    # Override which template repo to clone from (optional).
    template_repo: str | None = Field(default=None, examples=["my-org/app-template"])

    @field_validator("team_name")
    @classmethod
    def validate_team(cls, v: str) -> str:
        return _validate_slug(v, "team_name")

    @field_validator("app_name")
    @classmethod
    def validate_app(cls, v: str) -> str:
        return _validate_slug(v, "app_name")

    @property
    def resource_name(self) -> str:
        """Canonical name used for every resource (namespace, repo, ArgoCD app)."""
        return f"{self.team_name}-{self.app_name}"


class ProvisionResult(BaseModel):
    status: str
    github_repo: str
    namespace: str
    argocd_app: str
    grafana_dashboard: str
