"""Step implementations for all Mnemosyne BDD features."""

import time

import httpx
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.bdd.mock_services import DEMO_REPO

scenarios("../features")


@pytest.fixture
def state():
    return {}


# -- shared givens ----------------------------------------------------------------


@given("the Mnemosyne API is running")
def api_running(server_url):
    response = httpx.get(f"{server_url}/api/v1/health", timeout=10)
    assert response.status_code == 200


@given("a GitHub credential with repository read permissions is connected")
def github_connected(admin_api, state):
    response = admin_api.post("/api/v1/github/connect", json={"token": "ghp_bdd_token_ab12"})
    assert response.status_code in (200, 201), response.text
    state["connection_id"] = response.json()["id"]


@given(
    parsers.parse('the repository "{full_name}" is enabled with mode "{mode}"')
)
def repo_enabled(admin_api, state, full_name, mode):
    discovery = admin_api.post(f"/api/v1/repos/discover/{state['connection_id']}")
    assert discovery.status_code == 200, discovery.text
    repo = next(r for r in discovery.json() if r["full_name"] == full_name)
    patched = admin_api.patch(
        f"/api/v1/repos/{repo['id']}", json={"enabled": True, "indexing_mode": mode}
    )
    assert patched.status_code == 200, patched.text
    state["repo_id"] = repo["id"]


def _wait_for_sync(api, repo_id, timeout=60) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = api.get(f"/api/v1/repos/{repo_id}/sync-status")
        job = response.json()
        if job and job["status"] in ("succeeded", "failed"):
            return job
        time.sleep(0.5)
    raise TimeoutError("sync did not finish in time")


@given(parsers.parse('the repository "{full_name}" has been synced'))
def repo_synced(admin_api, state, full_name):
    github_connected(admin_api, state)
    repo_enabled(admin_api, state, full_name, "project_intelligence")
    status = admin_api.get(f"/api/v1/repos/{state['repo_id']}/sync-status").json()
    if status and status["status"] == "succeeded":
        return
    response = admin_api.post(f"/api/v1/repos/{state['repo_id']}/sync")
    if response.status_code not in (202, 409):
        raise AssertionError(response.text)
    job = _wait_for_sync(admin_api, state["repo_id"])
    assert job["status"] == "succeeded", job


# -- sync scenarios ------------------------------------------------------------------


@when("the admin starts a repository sync")
def admin_starts_sync(admin_api, state):
    response = admin_api.post(f"/api/v1/repos/{state['repo_id']}/sync")
    assert response.status_code in (202, 409), response.text
    state["job"] = _wait_for_sync(admin_api, state["repo_id"])


@then("the sync completes successfully")
def sync_succeeded(state):
    assert state["job"]["status"] == "succeeded", state["job"]


@then("the repository summary reports a README and OpenSpec content")
def summary_has_docs(api, state):
    summary = api.get(f"/api/v1/repos/{state['repo_id']}/summary").json()["summary"]
    assert summary["has_readme"] is True
    assert summary["has_openspec"] is True


@when("a non-admin user tries to start a sync")
def non_admin_sync(api, state):
    state["response"] = api.post(f"/api/v1/repos/{state['repo_id']}/sync")


@when("a caller without the mnemosyne entitlement lists repositories")
def unentitled_list(server_url, unentitled_token, state):
    state["response"] = httpx.get(
        f"{server_url}/api/v1/repos",
        headers={"Authorization": f"Bearer {unentitled_token}"},
        timeout=10,
    )


@then(parsers.parse("the request is rejected with status {status:d}"))
def rejected(state, status):
    assert state["response"].status_code == status, state["response"].text


# -- documentation scenarios -----------------------------------------------------------


@then(parsers.parse('the README.md is captured as type "{doc_type}"'))
def readme_captured(api, state, doc_type):
    docs = api.get(f"/api/v1/repos/{state['repo_id']}/docs").json()["items"]
    readme = next(d for d in docs if d["path"] == "README.md")
    assert readme["type"] == doc_type


@then(parsers.parse('OpenSpec change "{change_id}" is indexed with its proposal'))
def openspec_indexed(api, state, change_id):
    changes = api.get(f"/api/v1/repos/{state['repo_id']}/openspec").json()
    change = next(c for c in changes if c["change_id"] == change_id)
    assert change["proposal"]


@then(parsers.parse('a semantic search for "{query}" returns "{path}"'))
def semantic_search(api, state, query, path):
    matches = api.post(
        f"/api/v1/repos/{state['repo_id']}/search", json={"query": query}
    ).json()
    assert path in [m["path"] for m in matches], matches


# -- metrics scenarios ---------------------------------------------------------------


@then(parsers.parse('the issue list contains issue {number:d} in state "{issue_state}"'))
def issue_in_list(api, state, number, issue_state):
    issues = api.get(f"/api/v1/repos/{state['repo_id']}/issues").json()["items"]
    issue = next(i for i in issues if i["number"] == number)
    assert issue["state"] == issue_state


@then(parsers.parse("the average issue resolution time is {days:d} days"))
def avg_issue_resolution(api, state, days):
    metrics = api.get(f"/api/v1/repos/{state['repo_id']}/metrics").json()
    assert metrics["issue_metrics"]["avg_resolution_seconds"] == days * 86400


@then(parsers.parse('the pull request list contains merged PR {number:d} reviewed by "{reviewer}"'))
def pr_in_list(api, state, number, reviewer):
    prs = api.get(f"/api/v1/repos/{state['repo_id']}/pull-requests").json()["items"]
    pr = next(p for p in prs if p["number"] == number)
    assert pr["merged"] is True
    assert reviewer in pr["reviewers"]


@then(parsers.parse("the average PR merge time is {days:d} days"))
def avg_pr_merge(api, state, days):
    metrics = api.get(f"/api/v1/repos/{state['repo_id']}/metrics").json()
    assert metrics["pr_metrics"]["avg_time_to_merge_seconds"] == days * 86400


# -- context pack scenarios -------------------------------------------------------------


@when(parsers.parse('an agent requests a context pack for "{task}"'))
def request_context_pack(api, state, task):
    response = api.post(
        f"/api/v1/repos/{state['repo_id']}/context-pack", json={"query": task}
    )
    assert response.status_code == 200, response.text
    state["pack"] = response.json()


@then("the context pack includes relevant docs")
def pack_has_docs(state):
    assert state["pack"]["relevant_docs"], state["pack"]


@then(parsers.parse("the context pack includes issue {number:d}"))
def pack_has_issue(state, number):
    assert number in [i["number"] for i in state["pack"]["relevant_issues"]]


@then(parsers.parse("the context pack includes pull request {number:d}"))
def pack_has_pr(state, number):
    assert number in [p["number"] for p in state["pack"]["relevant_pull_requests"]]


@then(parsers.parse('the context pack includes OpenSpec change "{change_id}"'))
def pack_has_openspec(state, change_id):
    ids = [c["change_id"] for c in state["pack"]["relevant_openspec_changes"]]
    assert change_id in ids


# -- MCP scenarios --------------------------------------------------------------------


async def _mcp_call(mcp_url, token, tool=None, args=None):
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport

    transport = StreamableHttpTransport(f"{mcp_url}/mcp", auth=token) if token else (
        StreamableHttpTransport(f"{mcp_url}/mcp")
    )
    async with Client(transport) as client:
        if tool is None:
            return await client.list_tools()
        return await client.call_tool(tool, args or {})


@when("an agent connects to the MCP server with a valid token")
def mcp_connect(mcp_url, user_token, state):
    import asyncio

    state["tools"] = asyncio.run(_mcp_call(mcp_url, user_token))
    state["mcp_token"] = user_token


@then("the MCP tool list includes the mnemosyne tool suite")
def mcp_tools_listed(state):
    names = {t.name for t in state["tools"]}
    assert {"mnemosyne_list_repositories", "mnemosyne_build_context_pack"} <= names


@then(parsers.parse('calling "{tool}" returns the matforge summary'))
def mcp_summary(mcp_url, state, tool):
    import asyncio
    import json

    result = asyncio.run(
        _mcp_call(mcp_url, state["mcp_token"], tool, {"full_name": DEMO_REPO})
    )
    body = json.loads(result.content[0].text)
    assert body["full_name"] == DEMO_REPO
    assert body["summary"]["has_readme"] is True


@then(parsers.parse('calling "{tool}" returns the README content'))
def mcp_readme(mcp_url, state, tool):
    import asyncio
    import json

    result = asyncio.run(
        _mcp_call(mcp_url, state["mcp_token"], tool, {"full_name": DEMO_REPO})
    )
    body = json.loads(result.content[0].text)
    assert "Matforge" in body["content"]


@when("an agent connects to the MCP server without a token")
def mcp_connect_anonymous(mcp_url, state):
    state["mcp_url_anon"] = mcp_url


@then("MCP tool calls fail with an authentication error")
def mcp_anonymous_rejected(state):
    import asyncio

    from fastmcp.exceptions import ToolError

    with pytest.raises(Exception) as excinfo:
        asyncio.run(
            _mcp_call(state["mcp_url_anon"], None, "mnemosyne_list_repositories", {})
        )
    assert isinstance(excinfo.value, ToolError) or "unauth" in str(excinfo.value).lower()


@when(parsers.parse('an agent asks "{question}"'))
def ask_question(api, state, question):
    response = api.post(f"/api/v1/repos/{state['repo_id']}/ask", json={"question": question})
    assert response.status_code == 200, response.text
    state["answer"] = response.json()


@then("the answer is grounded with source citations")
def answer_grounded(state):
    answer = state["answer"]
    assert answer["grounded"] is True, answer
    assert answer["answer"]
    assert any(s["path"] == "docs/gpu-backend.md" for s in answer["sources"]), answer["sources"]
