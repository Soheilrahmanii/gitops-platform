"""
GitHubService — fully provisions a GitHub repo from a template.

Call order inside provision_repo:
  1. create_repo        — POST /repos/{tpl}/generate
  2. _wait_for_ready    — GET  /repos/{org}/{name}  (polls until default branch exists)
  3. set_branch_protection — PUT /repos/{org}/{name}/branches/main/protection
  4. add_codeowners     — PUT /repos/{org}/{name}/contents/CODEOWNERS
  5. add_topics         — PUT /repos/{org}/{name}/topics

Uses httpx.AsyncBaseTransport injection so every HTTP call can be mocked
in tests without a live network connection.
"""
import asyncio
import base64
import os
from contextlib import asynccontextmanager

import httpx

from models.provision import ProvisionRequest

_GITHUB_API = "https://api.github.com"


class GitHubService:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._token = os.environ["GITHUB_TOKEN"]
        self._org = os.environ["GITHUB_ORG"]
        self._template = os.environ["GITHUB_TEMPLATE_REPO"]
        self._transport = transport
        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    # ── public API ─────────────────────────────────────────────────────────────

    async def provision_repo(self, req: ProvisionRequest) -> str:
        """Full provisioning flow — creates repo and applies all platform settings."""
        repo_url = await self.create_repo(req)
        default_branch = await self._wait_for_ready(req.resource_name)
        await self.set_branch_protection(req.resource_name, default_branch)
        await self.add_codeowners(req.resource_name, req.team_name, default_branch)
        await self.add_topics(req.resource_name, [req.team_name, req.app_name, "gitops-platform"])
        return repo_url

    async def create_repo(self, req: ProvisionRequest) -> str:
        """Creates a repo from a template and returns its HTML URL."""
        template_owner, template_repo = (
            req.template_repo or self._template
        ).split("/", 1)

        async with self._client() as client:
            resp = await client.post(
                f"{_GITHUB_API}/repos/{template_owner}/{template_repo}/generate",
                json={
                    "owner": self._org,
                    "name": req.resource_name,
                    "description": req.description or f"Provisioned by GitOps Platform — {req.resource_name}",
                    "private": False,
                    "include_all_branches": False,
                },
            )
            resp.raise_for_status()
            return resp.json()["html_url"]

    async def set_branch_protection(self, repo_name: str, branch: str = "main") -> None:
        """Protects the default branch: requires PR review, blocks force-push."""
        async with self._client() as client:
            resp = await client.put(
                f"{_GITHUB_API}/repos/{self._org}/{repo_name}/branches/{branch}/protection",
                json={
                    "required_status_checks": None,
                    "enforce_admins": False,
                    "required_pull_request_reviews": {
                        "dismiss_stale_reviews": True,
                        "require_code_owner_reviews": True,
                        "required_approving_review_count": 1,
                    },
                    "restrictions": None,
                    "allow_force_pushes": False,
                    "allow_deletions": False,
                },
            )
            resp.raise_for_status()

    async def add_codeowners(self, repo_name: str, team_name: str, branch: str = "main") -> None:
        """Commits a CODEOWNERS file that routes reviews to the team."""
        content = f"* @{self._org}/{team_name}\n"
        encoded = base64.b64encode(content.encode()).decode()

        async with self._client() as client:
            resp = await client.put(
                f"{_GITHUB_API}/repos/{self._org}/{repo_name}/contents/CODEOWNERS",
                json={
                    "message": "chore: add CODEOWNERS [skip ci]",
                    "content": encoded,
                },
            )
            resp.raise_for_status()

    async def add_topics(self, repo_name: str, topics: list[str]) -> None:
        """Sets repository topics so the repo is discoverable in the org."""
        async with self._client() as client:
            resp = await client.put(
                f"{_GITHUB_API}/repos/{self._org}/{repo_name}/topics",
                json={"names": topics},
            )
            resp.raise_for_status()

    async def delete_repo(self, repo_name: str) -> None:
        """Deletes the repository. 404 is silently ignored (idempotent teardown)."""
        async with self._client() as client:
            resp = await client.delete(
                f"{_GITHUB_API}/repos/{self._org}/{repo_name}"
            )
            if resp.status_code not in (204, 404):
                resp.raise_for_status()

    # ── private helpers ────────────────────────────────────────────────────────

    async def _wait_for_ready(
        self,
        repo_name: str,
        *,
        max_retries: int = 10,
        delay: float = 3.0,
    ) -> str:
        """Polls until the repo exists and its default branch is available.

        GitHub takes a few seconds to copy template contents and create the
        default branch after a /generate call. Without this wait, branch
        protection and CODEOWNERS writes will 404.

        Returns the default branch name (e.g. 'main' or 'master').
        """
        async with self._client() as client:
            for _ in range(max_retries):
                resp = await client.get(
                    f"{_GITHUB_API}/repos/{self._org}/{repo_name}"
                )
                if resp.status_code == 200:
                    branch = resp.json().get("default_branch")
                    if branch:
                        branch_resp = await client.get(
                            f"{_GITHUB_API}/repos/{self._org}/{repo_name}/branches/{branch}"
                        )
                        if branch_resp.status_code == 200:
                            return branch
                await asyncio.sleep(delay)

        raise RuntimeError(
            f"Repository {repo_name} was not ready after "
            f"{max_retries} attempts ({max_retries * delay:.0f}s total)."
        )

    @asynccontextmanager
    async def _client(self):
        """Yields a configured AsyncClient, injecting the test transport if set."""
        async with httpx.AsyncClient(
            headers=self._headers,
            timeout=30,
            transport=self._transport,
        ) as client:
            yield client
