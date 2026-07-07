"""MCP interface tests (spec: mcp-interface). In-memory FastMCP client over fakes."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from app.domain.entities.document import Document
from app.domain.entities.issue import Issue
from app.domain.entities.openspec_change import OpenSpecChange
from app.domain.entities.repository import Repository
from app.domain.value_objects.enums import (
    DocumentType,
    IndexingMode,
    IssueState,
    OpenSpecStatus,
    RepositoryVisibility,
)
from app.domain.value_objects.full_name import RepositoryFullName
from app.domain.value_objects.identity import CallerIdentity
from app.interfaces.mcp.server import build_mcp
from tests.unit.interfaces.test_api_endpoints import build_fake_container

NOW = datetime(2026, 7, 7, tzinfo=UTC)

EXPECTED_TOOLS = {
    "mnemosyne_list_repositories",
    "mnemosyne_get_repository_summary",
    "mnemosyne_get_repository_tree",
    "mnemosyne_get_readme",
    "mnemosyne_get_docs_index",
    "mnemosyne_search_docs",
    "mnemosyne_get_openspec_context",
    "mnemosyne_list_issues",
    "mnemosyne_get_issue",
    "mnemosyne_search_issues",
    "mnemosyne_get_issue_resolution_metrics",
    "mnemosyne_list_pull_requests",
    "mnemosyne_get_pull_request",
    "mnemosyne_get_pr_review_metrics",
    "mnemosyne_find_stale_issues",
    "mnemosyne_find_stale_prs",
    "mnemosyne_build_context_pack",
    "mnemosyne_answer_from_repo_context",
}


async def entitled_caller() -> CallerIdentity:
    return CallerIdentity(subject="agent-1", entitlements=frozenset({"mnemosyne"}))


async def rejecting_caller() -> CallerIdentity:
    raise ToolError("unauthenticated: missing bearer token")


@pytest.fixture
def container():
    return build_fake_container()


@pytest.fixture
def mcp(container):
    return build_mcp(container, authenticate=entitled_caller)


async def seed_repo(container, *, synced=True, mode=IndexingMode.PROJECT_INTELLIGENCE,
                    enabled=True):
    repo = Repository(
        id=uuid4(), connection_id=uuid4(), github_id=1,
        full_name=RepositoryFullName("cyberdyne/a"), description="demo repo",
        visibility=RepositoryVisibility.PRIVATE, default_branch="main",
        primary_language="Python", archived=False, github_updated_at=NOW,
        enabled=enabled, indexing_mode=mode, last_synced_at=NOW if synced else None,
    )
    await container.repositories.save(repo)
    return repo


def payload(result):
    return json.loads(result.content[0].text)


class TestToolListing:
    async def test_all_spec_tools_registered(self, mcp):
        async with Client(mcp) as client:
            tools = {t.name for t in await client.list_tools()}
        assert tools >= EXPECTED_TOOLS


class TestAuth:
    async def test_unauthenticated_rejected(self, container):
        mcp = build_mcp(container, authenticate=rejecting_caller)
        async with Client(mcp) as client:
            with pytest.raises(ToolError, match="unauthenticated"):
                await client.call_tool("mnemosyne_list_repositories", {})


class TestStructuredErrors:
    async def test_unknown_repository(self, mcp):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "mnemosyne_get_repository_summary", {"full_name": "cyberdyne/nope"}
            )
        assert payload(result)["error"]["code"] == "unknown_repository"

    async def test_disabled_repository_treated_as_unknown(self, mcp, container):
        await seed_repo(container, enabled=False)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "mnemosyne_get_readme", {"full_name": "cyberdyne/a"}
            )
        assert payload(result)["error"]["code"] == "unknown_repository"

    async def test_unsynced_repository(self, mcp, container):
        await seed_repo(container, synced=False)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "mnemosyne_get_readme", {"full_name": "cyberdyne/a"}
            )
        assert payload(result)["error"]["code"] == "repository_not_synced"

    async def test_mode_excludes_content(self, mcp, container):
        await seed_repo(container, mode=IndexingMode.DOCS_ONLY)
        async with Client(mcp) as client:
            issues = await client.call_tool(
                "mnemosyne_list_issues", {"full_name": "cyberdyne/a"}
            )
            tree = await client.call_tool(
                "mnemosyne_get_repository_tree", {"full_name": "cyberdyne/a"}
            )
        assert payload(issues)["error"]["code"] == "mode_excludes_content"
        assert payload(tree)["error"]["code"] == "mode_excludes_content"


class TestHappyPaths:
    async def test_list_repositories_enabled_only(self, mcp, container):
        await seed_repo(container)
        async with Client(mcp) as client:
            result = await client.call_tool("mnemosyne_list_repositories", {})
        repos = payload(result)
        listed = repos if isinstance(repos, list) else [repos]
        assert listed[0]["full_name"] == "cyberdyne/a"
        assert listed[0]["last_synced_at"] is not None

    async def test_readme_and_docs_index(self, mcp, container):
        repo = await seed_repo(container)
        await container.documents.save(
            Document(
                id=uuid4(), repository_id=repo.id, path="README.md",
                type=DocumentType.README, title="Demo", content="# Demo",
                content_hash="h", last_commit_sha=None, captured_at=NOW,
            )
        )
        async with Client(mcp) as client:
            readme = await client.call_tool("mnemosyne_get_readme", {"full_name": "cyberdyne/a"})
            index = await client.call_tool(
                "mnemosyne_get_docs_index", {"full_name": "cyberdyne/a"}
            )
        assert payload(readme)["content"] == "# Demo"
        index_payload = payload(index)
        docs = index_payload if isinstance(index_payload, list) else [index_payload]
        assert docs[0]["type"] == "README"

    async def test_openspec_context(self, mcp, container):
        repo = await seed_repo(container)
        await container.openspec.save(
            OpenSpecChange(
                id=uuid4(), repository_id=repo.id, change_id="add-x",
                path="openspec/changes/add-x", status=OpenSpecStatus.ACTIVE,
                proposal="# P", tasks="- [ ] 1",
            )
        )
        async with Client(mcp) as client:
            result = await client.call_tool(
                "mnemosyne_get_openspec_context", {"full_name": "cyberdyne/a"}
            )
        body = payload(result)
        assert body["changes"][0]["change_id"] == "add-x"
        assert body["changes"][0]["status"] == "active"

    async def test_issue_tools(self, mcp, container):
        repo = await seed_repo(container)
        await container.issues.save_many(
            [
                Issue(
                    id=uuid4(), repository_id=repo.id, github_issue_id=1, number=42,
                    title="Add OpenCL backend", body="please", state=IssueState.OPEN,
                    author="alice", labels=["feature"], created_at=NOW,
                )
            ]
        )
        async with Client(mcp) as client:
            one = await client.call_tool(
                "mnemosyne_get_issue", {"full_name": "cyberdyne/a", "number": 42}
            )
            searched = await client.call_tool(
                "mnemosyne_search_issues", {"full_name": "cyberdyne/a", "query": "opencl"}
            )
            missing = await client.call_tool(
                "mnemosyne_get_issue", {"full_name": "cyberdyne/a", "number": 999}
            )
        assert payload(one)["body"] == "please"
        searched_payload = payload(searched)
        hits = searched_payload if isinstance(searched_payload, list) else [searched_payload]
        assert hits[0]["number"] == 42
        assert payload(missing)["error"]["code"] == "not_found"

    async def test_metrics_tools(self, mcp, container):
        repo = await seed_repo(container)
        await container.metrics_store.save(
            repo.id,
            issue_metrics={"avg_resolution_seconds": 3600},
            pr_metrics={"merge_rate": 0.8},
            summary={},
            computed_at=NOW.isoformat(),
        )
        # FakeMetricsStore.save stores kwargs; adapt shape for get()
        container.metrics_store.data[repo.id]["computed_at"] = NOW.isoformat()
        async with Client(mcp) as client:
            issue_metrics = await client.call_tool(
                "mnemosyne_get_issue_resolution_metrics", {"full_name": "cyberdyne/a"}
            )
            pr_metrics = await client.call_tool(
                "mnemosyne_get_pr_review_metrics", {"full_name": "cyberdyne/a"}
            )
        assert payload(issue_metrics)["avg_resolution_seconds"] == 3600
        assert payload(pr_metrics)["merge_rate"] == 0.8

    async def test_context_pack_tool(self, mcp, container):
        await seed_repo(container)
        async with Client(mcp) as client:
            result = await client.call_tool(
                "mnemosyne_build_context_pack",
                {"full_name": "cyberdyne/a", "task": "implement opencl backend"},
            )
        body = payload(result)
        assert body["repository"] == "cyberdyne/a"
        assert body["mode"] == "project_intelligence"
        assert "suggested_next_steps" in body

    async def test_answer_tool(self, mcp, container):
        from app.domain.ports.infra_ports import ChunkMatch

        await seed_repo(container)
        container.embeddings.matches = [
            ChunkMatch(
                document_id=uuid4(), path="README.md", title="R", doc_type="README",
                excerpt="hello", score=0.9,
            )
        ]
        async with Client(mcp) as client:
            result = await client.call_tool(
                "mnemosyne_answer_from_repo_context",
                {"full_name": "cyberdyne/a", "question": "what is this?"},
            )
        body = payload(result)
        assert body["grounded"] is True
        assert body["sources"][0]["path"] == "README.md"
