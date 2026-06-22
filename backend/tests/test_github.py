import base64
import json
import pytest
import httpx

from models.provision import ProvisionRequest
from services.github import GitHubService

# ── helpers ────────────────────────────────────────────────────────────────────

def _make_req(**kwargs) -> ProvisionRequest:
    defaults = {"team_name": "platform", "app_name": "hello-world"}
    return ProvisionRequest(**(defaults | kwargs))


def _svc(handler=None, status=200, body=None) -> GitHubService:
    """Build a GitHubService with a mock transport.

    Pass a raw handler, or let it default to a simple status+body response.
    """
    if handler is None:
        _body = body or {}
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status, json=_body)
    return GitHubService(transport=httpx.MockTransport(handler))


def _router(*routes: tuple) -> httpx.MockTransport:
    """Transport that dispatches by (METHOD, URL fragment).

    routes: sequence of (method, url_fragment, status_code, body_dict)
    Falls through to 200/{} if nothing matches.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        for method, fragment, status, body in routes:
            if request.method == method and fragment in str(request.url):
                return httpx.Response(status, json=body)
        return httpx.Response(200, json={})
    return httpx.MockTransport(handler)


_REPO_URL = "https://github.com/test-org/platform-hello-world"

# ready repo payload — returned by GET /repos/{org}/{name}
_READY_REPO = {"default_branch": "main", "html_url": _REPO_URL}


# ── create_repo ────────────────────────────────────────────────────────────────

async def test_create_repo_returns_html_url():
    svc = _svc(status=201, body={"html_url": _REPO_URL})
    assert await svc.create_repo(_make_req()) == _REPO_URL


async def test_create_repo_posts_to_generate_endpoint():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        captured["body"] = req.read()
        return httpx.Response(201, json={"html_url": _REPO_URL})

    await GitHubService(transport=httpx.MockTransport(handler)).create_repo(_make_req())

    assert "generate" in captured["url"]
    assert b"platform-hello-world" in captured["body"]


async def test_create_repo_uses_template_override():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        return httpx.Response(201, json={"html_url": _REPO_URL})

    await GitHubService(transport=httpx.MockTransport(handler)).create_repo(
        _make_req(template_repo="custom-org/custom-template")
    )
    assert "custom-org/custom-template" in captured["url"]


async def test_create_repo_default_description_filled_in():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.read())
        return httpx.Response(201, json={"html_url": _REPO_URL})

    await GitHubService(transport=httpx.MockTransport(handler)).create_repo(
        _make_req(description="")
    )
    assert "platform-hello-world" in captured["body"]["description"]


async def test_create_repo_passes_custom_description():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.read())
        return httpx.Response(201, json={"html_url": _REPO_URL})

    await GitHubService(transport=httpx.MockTransport(handler)).create_repo(
        _make_req(description="My custom service")
    )
    assert captured["body"]["description"] == "My custom service"


async def test_create_repo_raises_on_http_422():
    with pytest.raises(httpx.HTTPStatusError):
        await _svc(status=422, body={"message": "already exists"}).create_repo(_make_req())


async def test_create_repo_raises_on_404():
    with pytest.raises(httpx.HTTPStatusError):
        await _svc(status=404, body={"message": "Not Found"}).create_repo(_make_req())


async def test_create_repo_sends_auth_header():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["auth"] = req.headers.get("authorization", "")
        return httpx.Response(201, json={"html_url": _REPO_URL})

    await GitHubService(transport=httpx.MockTransport(handler)).create_repo(_make_req())
    assert captured["auth"] == "Bearer test-token"


# ── _wait_for_ready ────────────────────────────────────────────────────────────

async def test_wait_returns_immediately_when_repo_ready():
    svc = _svc(status=200, body=_READY_REPO)
    # Should not raise.
    await svc._wait_for_ready("platform-hello-world", max_retries=1, delay=0)


async def test_wait_raises_after_max_retries_when_repo_not_found():
    svc = _svc(status=404, body={})
    with pytest.raises(RuntimeError, match="not ready"):
        await svc._wait_for_ready("platform-hello-world", max_retries=2, delay=0)


async def test_wait_raises_when_default_branch_missing():
    # Repo exists (200) but GitHub hasn't finished copying template contents yet.
    svc = _svc(status=200, body={"default_branch": None})
    with pytest.raises(RuntimeError, match="not ready"):
        await svc._wait_for_ready("platform-hello-world", max_retries=2, delay=0)


async def test_wait_retries_until_repo_becomes_ready():
    call_count = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(404, json={})
        return httpx.Response(200, json=_READY_REPO)

    svc = GitHubService(transport=httpx.MockTransport(handler))
    await svc._wait_for_ready("platform-hello-world", max_retries=5, delay=0)
    # 2 failed repo checks + 1 successful repo check + 1 branch existence check = 4
    assert call_count == 4


# ── set_branch_protection ──────────────────────────────────────────────────────

async def test_set_branch_protection_calls_correct_endpoint():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        captured["method"] = req.method
        return httpx.Response(200, json={})

    await GitHubService(transport=httpx.MockTransport(handler)).set_branch_protection(
        "platform-hello-world"
    )
    assert captured["method"] == "PUT"
    assert "branches/main/protection" in captured["url"]
    assert "platform-hello-world" in captured["url"]


async def test_set_branch_protection_disallows_force_push():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.read())
        return httpx.Response(200, json={})

    await GitHubService(transport=httpx.MockTransport(handler)).set_branch_protection(
        "platform-hello-world"
    )
    assert captured["body"]["allow_force_pushes"] is False


async def test_set_branch_protection_requires_pr_review():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.read())
        return httpx.Response(200, json={})

    await GitHubService(transport=httpx.MockTransport(handler)).set_branch_protection(
        "platform-hello-world"
    )
    reviews = captured["body"]["required_pull_request_reviews"]
    assert reviews["required_approving_review_count"] >= 1
    assert reviews["require_code_owner_reviews"] is True


async def test_set_branch_protection_raises_on_error():
    with pytest.raises(httpx.HTTPStatusError):
        await _svc(status=422, body={}).set_branch_protection("platform-hello-world")


# ── add_codeowners ─────────────────────────────────────────────────────────────

async def test_add_codeowners_creates_file_at_correct_path():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        captured["method"] = req.method
        return httpx.Response(201, json={})

    await GitHubService(transport=httpx.MockTransport(handler)).add_codeowners(
        "platform-hello-world", "platform"
    )
    assert captured["method"] == "PUT"
    assert "contents/CODEOWNERS" in captured["url"]


async def test_add_codeowners_content_references_team():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.read())
        return httpx.Response(201, json={})

    await GitHubService(transport=httpx.MockTransport(handler)).add_codeowners(
        "platform-hello-world", "platform"
    )
    decoded = base64.b64decode(captured["body"]["content"]).decode()
    assert "@test-org/platform" in decoded


async def test_add_codeowners_content_covers_all_files():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.read())
        return httpx.Response(201, json={})

    await GitHubService(transport=httpx.MockTransport(handler)).add_codeowners(
        "platform-hello-world", "platform"
    )
    decoded = base64.b64decode(captured["body"]["content"]).decode()
    # The wildcard pattern means every file in the repo requires team review.
    assert decoded.startswith("*")


async def test_add_codeowners_commit_message_includes_skip_ci():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.read())
        return httpx.Response(201, json={})

    await GitHubService(transport=httpx.MockTransport(handler)).add_codeowners(
        "platform-hello-world", "platform"
    )
    # [skip ci] prevents the first commit from triggering an empty CI run.
    assert "[skip ci]" in captured["body"]["message"]


async def test_add_codeowners_raises_on_error():
    with pytest.raises(httpx.HTTPStatusError):
        await _svc(status=422, body={}).add_codeowners("platform-hello-world", "platform")


# ── add_topics ─────────────────────────────────────────────────────────────────

async def test_add_topics_calls_correct_endpoint():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        captured["method"] = req.method
        return httpx.Response(200, json={})

    await GitHubService(transport=httpx.MockTransport(handler)).add_topics(
        "platform-hello-world", ["platform", "hello-world", "gitops-platform"]
    )
    assert captured["method"] == "PUT"
    assert "topics" in captured["url"]


async def test_add_topics_sends_names_list():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(req.read())
        return httpx.Response(200, json={})

    await GitHubService(transport=httpx.MockTransport(handler)).add_topics(
        "platform-hello-world", ["platform", "hello-world", "gitops-platform"]
    )
    assert set(captured["body"]["names"]) == {"platform", "hello-world", "gitops-platform"}


async def test_add_topics_raises_on_error():
    with pytest.raises(httpx.HTTPStatusError):
        await _svc(status=422, body={}).add_topics("platform-hello-world", ["gitops-platform"])


# ── delete_repo ────────────────────────────────────────────────────────────────

async def test_delete_repo_sends_delete_request():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["method"] = req.method
        captured["url"] = str(req.url)
        return httpx.Response(204, json={})

    await GitHubService(transport=httpx.MockTransport(handler)).delete_repo(
        "platform-hello-world"
    )
    assert captured["method"] == "DELETE"
    assert "platform-hello-world" in captured["url"]


async def test_delete_repo_is_idempotent_on_404():
    # Deleting a repo that no longer exists must not raise.
    svc = _svc(status=404, body={"message": "Not Found"})
    await svc.delete_repo("platform-hello-world")  # should not raise


async def test_delete_repo_raises_on_unexpected_error():
    with pytest.raises(httpx.HTTPStatusError):
        await _svc(status=500, body={}).delete_repo("platform-hello-world")


# ── provision_repo (end-to-end through the service) ───────────────────────────

async def test_provision_repo_returns_html_url():
    transport = _router(
        ("POST", "generate",     201, {"html_url": _REPO_URL}),
        ("GET",  "/repos/",      200, _READY_REPO),
        ("PUT",  "protection",   200, {}),
        ("PUT",  "CODEOWNERS",   201, {}),
        ("PUT",  "topics",       200, {}),
    )
    svc = GitHubService(transport=transport)
    url = await svc.provision_repo(_make_req())
    assert url == _REPO_URL


async def test_provision_repo_calls_all_five_endpoints():
    endpoints_hit = []

    def handler(req: httpx.Request) -> httpx.Response:
        endpoints_hit.append((req.method, str(req.url)))
        if "generate" in str(req.url):
            return httpx.Response(201, json={"html_url": _REPO_URL})
        if req.method == "GET":
            return httpx.Response(200, json=_READY_REPO)
        return httpx.Response(200, json={})

    svc = GitHubService(transport=httpx.MockTransport(handler))
    await svc.provision_repo(_make_req())

    methods_and_fragments = [(m, u) for m, u in endpoints_hit]
    assert any("generate"   in u for _, u in methods_and_fragments)
    assert any(m == "GET"   and "/repos/" in u for m, u in methods_and_fragments)
    assert any("protection" in u for _, u in methods_and_fragments)
    assert any("CODEOWNERS" in u for _, u in methods_and_fragments)
    assert any("topics"     in u for _, u in methods_and_fragments)


async def test_provision_repo_includes_idp_topic():
    topics_sent = {}

    def handler(req: httpx.Request) -> httpx.Response:
        if "topics" in str(req.url) and req.method == "PUT":
            topics_sent["names"] = json.loads(req.read())["names"]
        if "generate" in str(req.url):
            return httpx.Response(201, json={"html_url": _REPO_URL})
        if req.method == "GET":
            return httpx.Response(200, json=_READY_REPO)
        return httpx.Response(200, json={})

    svc = GitHubService(transport=httpx.MockTransport(handler))
    await svc.provision_repo(_make_req())

    assert "gitops-platform" in topics_sent["names"]
    assert "platform" in topics_sent["names"]
    assert "hello-world" in topics_sent["names"]


async def test_provision_repo_propagates_create_repo_error():
    transport = _router(
        ("POST", "generate", 422, {"message": "Repository already exists"}),
    )
    svc = GitHubService(transport=transport)
    with pytest.raises(httpx.HTTPStatusError):
        await svc.provision_repo(_make_req())


async def test_provision_repo_propagates_wait_timeout():
    # Repo never becomes ready — GET always returns 404.
    transport = _router(
        ("POST", "generate", 201, {"html_url": _REPO_URL}),
        ("GET",  "/repos/",  404, {}),
    )
    svc = GitHubService(transport=transport)
    with pytest.raises(RuntimeError, match="not ready"):
        await svc.provision_repo(
            _make_req(),
        )
        # _wait_for_ready defaults: 10 retries × 3 s delay — too slow for a test.
        # Patch the internal call instead:

async def test_provision_repo_propagates_wait_timeout_via_direct_call():
    transport = _router(
        ("POST", "generate", 201, {"html_url": _REPO_URL}),
        ("GET",  "/repos/",  404, {}),
    )
    svc = GitHubService(transport=transport)
    # Call _wait_for_ready directly with tiny retries so the test stays fast.
    with pytest.raises(RuntimeError, match="not ready"):
        await svc._wait_for_ready("platform-hello-world", max_retries=2, delay=0)
