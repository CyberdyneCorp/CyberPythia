"""Integrated MCP tests for the cross-repo agent tools (spec: mcp-interface).

Each test spins up the real FastMCP server (in-memory Client) and calls the tool,
exercising registration + serialization + the CrossRepoService end to end.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastmcp import Client

from app.domain.entities.issue import Issue
from app.domain.entities.pull_request import PullRequest
from app.domain.entities.repository import Repository
from app.domain.value_objects.enums import (
    IndexingMode,
    IssueState,
    PullRequestState,
    RepositoryVisibility,
)
from app.domain.value_objects.full_name import RepositoryFullName
from app.interfaces.mcp.server import build_mcp
from tests.unit.interfaces.test_api_endpoints import build_fake_container
from tests.unit.interfaces.test_mcp_server import entitled_caller, payload

NOW = datetime(2026, 7, 9, tzinfo=UTC)


def _repo(owner, name, *, synced=True, desc="d", lang="Python") -> Repository:
    return Repository(
        id=uuid4(), connection_id=uuid4(), github_id=hash((owner, name)) % 100000,
        full_name=RepositoryFullName(f"{owner}/{name}"), description=desc,
        visibility=RepositoryVisibility.PRIVATE, default_branch="main",
        primary_language=lang, archived=False, github_updated_at=NOW,
        enabled=True, indexing_mode=IndexingMode.PROJECT_INTELLIGENCE,
        last_synced_at=NOW if synced else None,
    )


def _issue(repo_id, number, *, updated, state=IssueState.OPEN) -> Issue:
    return Issue(
        id=uuid4(), repository_id=repo_id, github_issue_id=number, number=number,
        title=f"issue {number}", body="b", state=state, author="alice",
        labels=["bug"], created_at=updated, updated_at=updated,
    )


def _pr(repo_id, number, *, updated, state=PullRequestState.OPEN, merged=False) -> PullRequest:
    return PullRequest(
        id=uuid4(), repository_id=repo_id, github_pr_id=number, number=number,
        title=f"pr {number}", body="b", state=state, merged=merged, author="bob",
        created_at=updated, updated_at=updated,
    )


@pytest.fixture
def container():
    return build_fake_container()


@pytest.fixture
def mcp(container):
    return build_mcp(container, authenticate=entitled_caller)


async def _seed(container):
    auth = _repo("CyberdyneCorp", "auth", desc="authentication service", lang="Rust")
    pythia = _repo("CyberdyneCorp", "pythia", desc="MCP context server")
    other = _repo("aminitech", "chatbb", desc="chatbot backend")
    for r in (auth, pythia, other):
        await container.repositories.save(r)
    # auth: one stale open issue (100d), one fresh; pythia: fresh PR; aminitech: stale PR
    await container.issues.save_many([
        _issue(auth.id, 1, updated=NOW - timedelta(days=100)),
        _issue(auth.id, 2, updated=NOW - timedelta(days=1)),
        _issue(other.id, 9, updated=NOW - timedelta(days=200)),
    ])
    await container.pull_requests.save_many([
        _pr(pythia.id, 5, updated=NOW - timedelta(days=1)),
        _pr(other.id, 7, updated=NOW - timedelta(days=90)),
    ])
    return auth, pythia, other


class TestFindRepositories:
    async def test_fuzzy_resolve_by_name(self, mcp, container):
        await _seed(container)
        async with Client(mcp) as c:
            res = await c.call_tool("mnemosyne_find_repositories", {"query": "auth"})
        body = payload(res)
        assert body[0]["full_name"] == "CyberdyneCorp/auth"  # best match ranks first

    async def test_fuzzy_resolve_by_description(self, mcp, container):
        await _seed(container)
        async with Client(mcp) as c:
            res = await c.call_tool("mnemosyne_find_repositories", {"query": "chatbot"})
        assert payload(res)[0]["full_name"] == "aminitech/chatbb"


class TestStaleFinders:
    async def test_stale_issues_all_repos(self, mcp, container):
        await _seed(container)
        async with Client(mcp) as c:
            res = await c.call_tool("mnemosyne_find_stale_issues_across_repos", {})
        body = payload(res)
        # the 100d and 200d issues are stale; the 1d one is not; oldest first
        assert [(i["full_name"], i["number"]) for i in body] == [
            ("aminitech/chatbb", 9), ("CyberdyneCorp/auth", 1),
        ]

    async def test_stale_issues_org_scoped(self, mcp, container):
        await _seed(container)
        async with Client(mcp) as c:
            res = await c.call_tool(
                "mnemosyne_find_stale_issues_across_repos", {"organization": "CyberdyneCorp"}
            )
        body = payload(res)
        assert {i["full_name"] for i in body} == {"CyberdyneCorp/auth"}

    async def test_stale_prs_all_repos(self, mcp, container):
        await _seed(container)
        async with Client(mcp) as c:
            res = await c.call_tool("mnemosyne_find_stale_prs_across_repos", {})
        body = payload(res)
        assert [(p["full_name"], p["number"]) for p in body] == [("aminitech/chatbb", 7)]


class TestRecentActivity:
    async def test_recent_activity_shape(self, mcp, container):
        await _seed(container)
        async with Client(mcp) as c:
            res = await c.call_tool("mnemosyne_get_recent_activity", {})
        body = payload(res)
        assert {r["full_name"] for r in body["recently_synced"]} == {
            "CyberdyneCorp/auth", "CyberdyneCorp/pythia", "aminitech/chatbb"
        }
        # most recent issue first (the 1d one)
        assert body["recent_issues"][0]["number"] == 2
        assert body["recent_pull_requests"][0]["number"] == 5


class TestSearchAll:
    async def test_search_docs_global(self, mcp, container):
        auth, *_ = await _seed(container)
        from app.domain.ports.infra_ports import ChunkMatch

        container.embeddings.global_matches = [
            ChunkMatch(document_id=uuid4(), path="README.md", title="Auth",
                       doc_type="readme", excerpt="how auth works", score=0.9,
                       repository_id=auth.id),
        ]
        async with Client(mcp) as c:
            res = await c.call_tool("mnemosyne_search_all", {"query": "auth", "kind": "docs"})
        body = payload(res)
        assert body[0]["full_name"] == "CyberdyneCorp/auth"  # repo_id mapped to name
        assert body[0]["title"] == "Auth"

    async def test_search_issues_keyword(self, mcp, container):
        await _seed(container)  # issues titled "issue N"; search matches on title text
        async with Client(mcp) as c:
            res = await c.call_tool(
                "mnemosyne_search_all", {"query": "issue", "kind": "issues"}
            )
        body = payload(res)
        assert body and all("issue" in r["title"].lower() for r in body)
        assert all("full_name" in r for r in body)

    async def test_search_unknown_kind(self, mcp, container):
        await _seed(container)
        async with Client(mcp) as c:
            res = await c.call_tool("mnemosyne_search_all", {"query": "x", "kind": "bogus"})
        assert payload(res)["error"]["code"] == "invalid_kind"


class TestRepositoryMetrics:
    async def test_metrics_present(self, mcp, container):
        auth, *_ = await _seed(container)
        container.metrics_store.data[auth.id] = {"issue_metrics": {"open_count": 1}}
        async with Client(mcp) as c:
            res = await c.call_tool(
                "mnemosyne_get_repository_metrics", {"full_name": "CyberdyneCorp/auth"}
            )
        body = payload(res)
        assert body["metrics"]["issue_metrics"]["open_count"] == 1

    async def test_metrics_absent(self, mcp, container):
        await _seed(container)  # pythia has no metrics row
        async with Client(mcp) as c:
            res = await c.call_tool(
                "mnemosyne_get_repository_metrics", {"full_name": "CyberdyneCorp/pythia"}
            )
        assert payload(res)["error"]["code"] == "no_metrics"


class TestCapabilities:
    async def _seed_caps(self, container):
        from app.domain.entities.document import Document
        from app.domain.entities.openspec_change import OpenSpecChange
        from app.domain.value_objects.enums import DocumentType, OpenSpecStatus

        auth = _repo("CyberdyneCorp", "auth")
        await container.repositories.save(auth)
        await container.openspec.save(OpenSpecChange(
            id=uuid4(), repository_id=auth.id, change_id="add-login", path="p",
            status=OpenSpecStatus.ACTIVE, affected_specs=["authentication", "sessions"],
        ))
        await container.documents.save(Document(
            id=uuid4(), repository_id=auth.id, path="README.md", type=DocumentType.README,
            title="Auth Service", content="c", content_hash="h", last_commit_sha=None,
        ))
        await container.metrics_store.save(
            auth.id, computed_at=NOW.isoformat(),
            issue_metrics={"open_count": 4, "closed_count": 10, "by_label": {"bug": 3}},
            pr_metrics={"open_count": 1, "merged_count": 9}, summary={},
        )
        return auth

    async def test_repository_capabilities(self, mcp, container):
        await self._seed_caps(container)
        async with Client(mcp) as c:
            res = await c.call_tool(
                "mnemosyne_get_repository_capabilities", {"full_name": "CyberdyneCorp/auth"}
            )
        body = payload(res)
        assert body["capabilities"] == ["authentication", "sessions"]
        assert body["issues"]["bugs"] == 3
        assert "Auth Service" in body["documentation_topics"]

    async def test_openspec_coverage_partitions_repos(self, mcp, container):
        # auth has openspec (seeded change); add a second repo without any openspec.
        auth = await self._seed_caps(container)
        _ = auth
        plain = _repo("CyberdyneCorp", "plain")
        await container.repositories.save(plain)
        await container.metrics_store.save(
            plain.id, computed_at=NOW.isoformat(),
            issue_metrics={}, pr_metrics={},
            summary={"has_openspec": False, "openspec_changes": 0},
        )
        async with Client(mcp) as c:
            with_os = payload(await c.call_tool(
                "mnemosyne_list_repositories_with_openspec", {"organization": "CyberdyneCorp"}
            ))
            missing = payload(await c.call_tool(
                "mnemosyne_list_repositories_missing_openspec", {"organization": "CyberdyneCorp"}
            ))
        assert {r["full_name"] for r in with_os} == {"CyberdyneCorp/auth"}
        assert "CyberdyneCorp/plain" in {r["full_name"] for r in missing}

    async def test_organization_capabilities(self, mcp, container):
        await self._seed_caps(container)
        async with Client(mcp) as c:
            res = await c.call_tool(
                "mnemosyne_get_organization_capabilities", {"organization": "CyberdyneCorp"}
            )
        body = payload(res)
        assert body["repositories"] == 1
        assert "authentication" in body["capabilities"]
        assert body["total_open_bugs"] == 3

    async def test_feature_document(self, mcp, container):
        repo = await self._seed_caps(container)
        _ = repo
        async with Client(mcp) as c:
            res = await c.call_tool(
                "mnemosyne_generate_feature_document", {"full_name": "CyberdyneCorp/auth"}
            )
        body = payload(res)
        assert "document" in body and isinstance(body["document"], str)


class TestReadiness:
    async def _seed_ready(self, container, *, ci=True, tests=True):
        from app.domain.entities.document import Document
        from app.domain.entities.openspec_change import OpenSpecChange
        from app.domain.entities.source_file import SourceFile
        from app.domain.value_objects.enums import DocumentType, OpenSpecStatus

        repo = Repository(
            id=uuid4(), connection_id=uuid4(), github_id=7,
            full_name=RepositoryFullName("CyberdyneCorp/ready"), description="d",
            visibility=RepositoryVisibility.PRIVATE, default_branch="main",
            primary_language="Python", archived=False, github_updated_at=NOW,
            enabled=True, indexing_mode=IndexingMode.CODE_METADATA, last_synced_at=NOW,
        )
        await container.repositories.save(repo)
        paths = []
        if ci:
            paths.append(".github/workflows/ci.yml")
        if tests:
            paths.append("tests/test_app.py")
        files = [
            SourceFile(id=uuid4(), repository_id=repo.id, path=p, extension="x",
                       language="Python", size_bytes=1, sha="s")
            for p in paths
        ]
        await container.files.replace_tree(repo.id, files)
        await container.openspec.save(OpenSpecChange(
            id=uuid4(), repository_id=repo.id, change_id="c", path="p",
            status=OpenSpecStatus.ACTIVE, affected_specs=["core"]))
        for t, title in [(DocumentType.README, "R"), (DocumentType.DOCS, "Guide")]:
            await container.documents.save(Document(
                id=uuid4(), repository_id=repo.id, path=f"{title}.md", type=t,
                title=title, content="c", content_hash="h", last_commit_sha=None))
        await container.metrics_store.save(
            repo.id, computed_at=NOW.isoformat(),
            issue_metrics={"open_count": 2, "closed_count": 4, "by_label": {}},
            pr_metrics={"open_count": 0, "merged_count": 6}, summary={})
        return repo

    async def test_repository_readiness_ready(self, mcp, container):
        await self._seed_ready(container)
        async with Client(mcp) as c:
            res = payload(await c.call_tool(
                "mnemosyne_get_repository_readiness", {"full_name": "CyberdyneCorp/ready"}))
        assert res["gate"] == "READY"
        assert res["ready_checks"]["ci"] == "met"

    async def test_readiness_mvp_without_ci(self, mcp, container):
        await self._seed_ready(container, ci=False)
        async with Client(mcp) as c:
            res = payload(await c.call_tool(
                "mnemosyne_get_repository_readiness", {"full_name": "CyberdyneCorp/ready"}))
        assert res["gate"] == "MVP"
        assert "ci" in res["missing_for_ready"]

    async def test_organization_readiness_distribution(self, mcp, container):
        await self._seed_ready(container)
        async with Client(mcp) as c:
            res = payload(await c.call_tool(
                "mnemosyne_get_organization_readiness", {"organization": "CyberdyneCorp"}))
        assert res["distribution"]["READY"] == 1
        assert res["total"] == 1

    async def test_readiness_history_and_regressions_tools(self, mcp, container):
        from datetime import UTC, date, datetime

        from app.domain.entities.readiness_snapshot import ReadinessSnapshot

        repo = await self._seed_ready(container)
        ts = datetime(2026, 7, 9, tzinfo=UTC)
        await container.readiness_history.record(
            ReadinessSnapshot(repo.id, date(2026, 7, 8), ts, "DONE"))
        await container.readiness_history.record(
            ReadinessSnapshot(repo.id, date(2026, 7, 9), ts, "READY"))
        async with Client(mcp) as c:
            hist = payload(await c.call_tool(
                "mnemosyne_get_readiness_history", {"full_name": "CyberdyneCorp/ready"}))
            regs = payload(await c.call_tool(
                "mnemosyne_get_readiness_regressions", {"organization": "CyberdyneCorp"}))
        assert [h["gate"] for h in hist["history"]] == ["DONE", "READY"]
        assert regs["regressions"][0]["from_gate"] == "DONE"
        assert regs["regressions"][0]["to_gate"] == "READY"
