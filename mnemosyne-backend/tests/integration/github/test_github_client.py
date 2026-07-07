"""GitHub client tests against recorded fixtures (HTTP mocked with respx)."""

import httpx
import pytest
import respx

from app.domain.ports.github_port import GitHubAuthError, GitHubNotFoundError
from app.infrastructure.github.client import API_BASE, GitHubClient

TOKEN = "ghp_test"


class MemoryStorage:
    def __init__(self):
        self.objects = {}

    async def put_json(self, key, payload):
        self.objects[key] = payload

    async def get_json(self, key):
        return self.objects[key]


@pytest.fixture
def storage():
    return MemoryStorage()


@respx.mock
async def test_list_repositories_paginates(storage):
    page1 = [
        {
            "id": 1,
            "full_name": "cyberdyne/a",
            "visibility": "private",
            "default_branch": "main",
            "language": "Python",
            "archived": False,
            "updated_at": "2026-07-01T00:00:00Z",
        }
    ]
    page2 = [
        {
            "id": 2,
            "full_name": "cyberdyne/b",
            "private": False,
            "default_branch": "main",
            "archived": True,
            "updated_at": None,
        }
    ]
    respx.get(f"{API_BASE}/user/repos").mock(
        side_effect=[
            httpx.Response(
                200,
                json=page1,
                headers={"Link": f'<{API_BASE}/user/repos?page=2>; rel="next"'},
            ),
            httpx.Response(200, json=page2),
        ]
    )
    repos = await GitHubClient(storage=storage).list_repositories(TOKEN)
    assert [r.full_name for r in repos] == ["cyberdyne/a", "cyberdyne/b"]
    assert repos[0].visibility == "private"
    assert repos[1].visibility == "public"  # derived from `private: false`
    assert repos[1].archived


@respx.mock
async def test_issues_snapshot_raw_and_exclude_flag(storage):
    respx.get(f"{API_BASE}/repos/cyberdyne/a/issues").respond(
        json=[
            {
                "id": 11,
                "number": 1,
                "title": "bug",
                "state": "open",
                "user": {"login": "alice"},
                "labels": [{"name": "bug"}],
                "assignees": [],
                "comments": 2,
                "created_at": "2026-06-01T00:00:00Z",
            },
            {
                "id": 12,
                "number": 2,
                "title": "pr disguised as issue",
                "state": "open",
                "user": {"login": "bob"},
                "labels": [],
                "assignees": [],
                "pull_request": {"url": "..."},
                "created_at": "2026-06-02T00:00:00Z",
            },
        ]
    )
    client = GitHubClient(storage=storage)
    issues = await client.list_issues(TOKEN, "cyberdyne/a")
    assert len(issues) == 2
    assert not issues[0].is_pull_request
    assert issues[1].is_pull_request  # caller filters PRs out (spec: issues capture)
    assert "raw/github/repos/cyberdyne/a/issues.json" in storage.objects


@respx.mock
async def test_pull_requests_first_review_and_reviewers(storage):
    respx.get(f"{API_BASE}/repos/cyberdyne/a/pulls").respond(
        json=[
            {
                "id": 21,
                "number": 5,
                "title": "feat",
                "state": "closed",
                "user": {"login": "bob"},
                "created_at": "2026-06-01T00:00:00Z",
                "merged_at": "2026-06-03T00:00:00Z",
                "closed_at": "2026-06-03T00:00:00Z",
            }
        ]
    )
    respx.get(f"{API_BASE}/repos/cyberdyne/a/pulls/5/reviews").respond(
        json=[
            {"user": {"login": "carol"}, "state": "APPROVED", "submitted_at": "2026-06-02T00:00:00Z"},
            {"user": {"login": "dave"}, "state": "COMMENTED", "submitted_at": "2026-06-02T12:00:00Z"},
        ]
    )
    prs = await GitHubClient(storage=storage).list_pull_requests(TOKEN, "cyberdyne/a")
    assert prs[0].merged and prs[0].state == "merged"
    assert prs[0].reviewers == ["carol", "dave"]
    assert prs[0].first_review_at.isoformat() == "2026-06-02T00:00:00+00:00"


@respx.mock
async def test_tree_marks_binaries():
    respx.get(f"{API_BASE}/repos/cyberdyne/a/git/trees/main").respond(
        json={
            "tree": [
                {"type": "blob", "path": "src/app.py", "sha": "s1", "size": 10},
                {"type": "blob", "path": "logo.png", "sha": "s2", "size": 999},
                {"type": "tree", "path": "src"},
            ]
        }
    )
    files = await GitHubClient().get_tree(TOKEN, "cyberdyne/a", "main")
    assert [f.path for f in files] == ["src/app.py", "logo.png"]
    assert not files[0].is_binary
    assert files[1].is_binary


@respx.mock
async def test_file_content_base64_decoding():
    respx.get(f"{API_BASE}/repos/cyberdyne/a/contents/README.md").respond(
        json={"encoding": "base64", "content": "IyBIZWxsbw=="}
    )
    content = await GitHubClient().get_file_content(TOKEN, "cyberdyne/a", "README.md")
    assert content == "# Hello"


@respx.mock
async def test_401_raises_auth_error():
    respx.get(f"{API_BASE}/repos/cyberdyne/a").respond(401)
    with pytest.raises(GitHubAuthError):
        await GitHubClient().get_repository(TOKEN, "cyberdyne/a")


@respx.mock
async def test_404_raises_not_found():
    respx.get(f"{API_BASE}/repos/cyberdyne/gone").respond(404)
    with pytest.raises(GitHubNotFoundError):
        await GitHubClient().get_repository(TOKEN, "cyberdyne/gone")


@respx.mock
async def test_rate_limit_backoff_then_success():
    route = respx.get(f"{API_BASE}/repos/cyberdyne/a")
    route.side_effect = [
        httpx.Response(
            403,
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "0"},
            text="API rate limit exceeded",
        ),
        httpx.Response(
            200,
            json={
                "id": 1,
                "full_name": "cyberdyne/a",
                "visibility": "private",
                "default_branch": "main",
                "archived": False,
            },
        ),
    ]
    repo = await GitHubClient().get_repository(TOKEN, "cyberdyne/a")
    assert repo.full_name == "cyberdyne/a"
    assert route.call_count == 2
