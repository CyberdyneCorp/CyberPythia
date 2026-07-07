"""Coverage for the remaining MCP tools and the default bearer authenticator."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from app.domain.entities.pull_request import PullRequest
from app.domain.entities.source_file import SourceFile
from app.domain.ports.auth_port import AuthUnavailableError, TokenInvalidError
from app.domain.ports.infra_ports import ChunkMatch
from app.domain.value_objects.enums import IndexingMode, PullRequestState
from app.domain.value_objects.identity import CallerIdentity
from app.interfaces.mcp.server import build_mcp
from tests.unit.interfaces.test_api_endpoints import build_fake_container
from tests.unit.interfaces.test_mcp_server import entitled_caller, payload, seed_repo

NOW = datetime(2026, 7, 7, tzinfo=UTC)


@pytest.fixture
def container():
    return build_fake_container()


@pytest.fixture
def mcp(container):
    return build_mcp(container, authenticate=entitled_caller)


def as_list(body):
    return body if isinstance(body, list) else [body]


class TestRemainingTools:
    async def test_summary_with_metrics(self, mcp, container):
        repo = await seed_repo(container)
        await container.metrics_store.save(
            repo.id, issue_metrics={}, pr_metrics={}, summary={"has_readme": True},
            computed_at=NOW.isoformat(),
        )
        async with Client(mcp) as client:
            result = await client.call_tool(
                "mnemosyne_get_repository_summary", {"full_name": "cyberdyne/a"}
            )
        body = payload(result)
        assert body["summary"] == {"has_readme": True}
        assert body["indexing_mode"] == "project_intelligence"

    async def test_tree_happy_path(self, mcp, container):
        repo = await seed_repo(container, mode=IndexingMode.CODE_METADATA)
        await container.files.replace_tree(
            repo.id,
            [
                SourceFile(
                    id=uuid4(), repository_id=repo.id, path="pyproject.toml",
                    extension="toml", language=None, size_bytes=5, sha="s",
                    is_important=True, important_kind="dependency_manifest",
                )
            ],
        )
        async with Client(mcp) as client:
            result = await client.call_tool(
                "mnemosyne_get_repository_tree", {"full_name": "cyberdyne/a"}
            )
        body = payload(result)
        assert body["files"][0]["important_kind"] == "dependency_manifest"

    async def test_search_docs(self, mcp, container):
        await seed_repo(container)
        container.embeddings.matches = [
            ChunkMatch(
                document_id=uuid4(), path="docs/a.md", title="A", doc_type="DOCS",
                excerpt="x", score=0.7,
            )
        ]
        async with Client(mcp) as client:
            result = await client.call_tool(
                "mnemosyne_search_docs", {"full_name": "cyberdyne/a", "query": "x"}
            )
        assert as_list(payload(result))[0]["path"] == "docs/a.md"

    async def test_readme_missing(self, mcp, container):
        await seed_repo(container)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "mnemosyne_get_readme", {"full_name": "cyberdyne/a"}
            )
        assert payload(result)["error"]["code"] == "not_found"

    async def test_pull_request_tools(self, mcp, container):
        repo = await seed_repo(container)
        await container.pull_requests.save_many(
            [
                PullRequest(
                    id=uuid4(), repository_id=repo.id, github_pr_id=1, number=61,
                    title="Refactor backend", body="details", state=PullRequestState.OPEN,
                    merged=False, author="bob", created_at=NOW - timedelta(days=60),
                    updated_at=NOW - timedelta(days=45),
                )
            ]
        )
        async with Client(mcp) as client:
            listed = await client.call_tool(
                "mnemosyne_list_pull_requests", {"full_name": "cyberdyne/a"}
            )
            one = await client.call_tool(
                "mnemosyne_get_pull_request", {"full_name": "cyberdyne/a", "number": 61}
            )
            missing = await client.call_tool(
                "mnemosyne_get_pull_request", {"full_name": "cyberdyne/a", "number": 9}
            )
            stale = await client.call_tool(
                "mnemosyne_find_stale_prs", {"full_name": "cyberdyne/a"}
            )
        assert as_list(payload(listed))[0]["number"] == 61
        assert payload(one)["body"] == "details"
        assert payload(missing)["error"]["code"] == "not_found"
        assert as_list(payload(stale))[0]["number"] == 61

    async def test_stale_issues(self, mcp, container):
        from app.domain.entities.issue import Issue
        from app.domain.value_objects.enums import IssueState

        repo = await seed_repo(container)
        await container.issues.save_many(
            [
                Issue(
                    id=uuid4(), repository_id=repo.id, github_issue_id=1, number=7,
                    title="old", body=None, state=IssueState.OPEN, author="a",
                    created_at=NOW - timedelta(days=100),
                    updated_at=NOW - timedelta(days=90),
                )
            ]
        )
        async with Client(mcp) as client:
            result = await client.call_tool(
                "mnemosyne_find_stale_issues", {"full_name": "cyberdyne/a"}
            )
        assert as_list(payload(result))[0]["number"] == 7

    async def test_metrics_not_computed(self, mcp, container):
        await seed_repo(container)
        async with Client(mcp) as client:
            issue_metrics = await client.call_tool(
                "mnemosyne_get_issue_resolution_metrics", {"full_name": "cyberdyne/a"}
            )
            pr_metrics = await client.call_tool(
                "mnemosyne_get_pr_review_metrics", {"full_name": "cyberdyne/a"}
            )
        assert payload(issue_metrics)["error"]["code"] == "not_found"
        assert payload(pr_metrics)["error"]["code"] == "not_found"

    async def test_mode_excludes_prs(self, mcp, container):
        await seed_repo(container, mode=IndexingMode.DOCS_ONLY)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "mnemosyne_list_pull_requests", {"full_name": "cyberdyne/a"}
            )
        assert payload(result)["error"]["code"] == "mode_excludes_content"


class TestDefaultAuthenticator:
    """Exercises the header-based bearer path by faking get_http_headers."""

    @pytest.fixture
    def patched_headers(self, monkeypatch):
        state = {"headers": {}}

        def fake_get_http_headers(**kw):
            return state["headers"]

        monkeypatch.setattr(
            "app.interfaces.mcp.server.get_http_headers", fake_get_http_headers
        )
        return state

    async def call(self, container):
        mcp = build_mcp(container)  # default authenticator
        async with Client(mcp) as client:
            return await client.call_tool("mnemosyne_list_repositories", {})

    async def test_missing_header_rejected(self, container, patched_headers):
        with pytest.raises(ToolError, match="missing bearer"):
            await self.call(container)

    async def test_invalid_token_rejected_and_audited(self, container, patched_headers):
        patched_headers["headers"] = {"authorization": "Bearer bogus"}
        with pytest.raises(ToolError, match="invalid token"):
            await self.call(container)
        assert container.audit_port.records[-1].outcome == "denied"

    async def test_unentitled_rejected(self, container, patched_headers):
        patched_headers["headers"] = {"authorization": "Bearer unentitled-token"}
        with pytest.raises(ToolError, match="missing_entitlement"):
            await self.call(container)

    async def test_entitled_token_passes(self, container, patched_headers):
        patched_headers["headers"] = {"authorization": "Bearer agent-token"}
        result = await self.call(container)
        assert result is not None

    async def test_auth_plane_down(self, container, patched_headers):
        patched_headers["headers"] = {"authorization": "Bearer auth-down"}
        with pytest.raises(ToolError, match="auth_unavailable"):
            await self.call(container)
