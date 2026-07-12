"""Agent memory use case (spec: agent-memory)."""

from uuid import UUID, uuid4

import pytest

from app.application.errors import UnknownResourceError
from app.application.use_cases.memory import MemoryService
from app.domain.entities.repository import Repository
from app.domain.services.org_scope import set_allowed_organizations
from app.domain.value_objects.enums import RepositoryVisibility
from app.domain.value_objects.full_name import RepositoryFullName
from tests.unit.application.fakes import FakeMemoryPort, FakeRepositoryPort


def _repo(full_name="cyberdyne/a", enabled=True) -> Repository:
    return Repository(
        id=uuid4(), connection_id=uuid4(), github_id=1,
        full_name=RepositoryFullName(full_name), description=None,
        visibility=RepositoryVisibility.PRIVATE, default_branch="main",
        primary_language=None, archived=False, github_updated_at=None, enabled=enabled,
    )


async def test_remember_then_recall_repository():
    repos, mem = FakeRepositoryPort(), FakeMemoryPort()
    await repos.save(_repo())
    svc = MemoryService(mem, repos)
    created = await svc.remember_repository(
        "cyberdyne/a", content="  use uv, not pip  ", kind="convention", author="agent-1")
    assert created["kind"] == "convention"
    assert created["content"] == "use uv, not pip"  # trimmed
    recalled = await svc.recall_repository("cyberdyne/a")
    assert [m["id"] for m in recalled["memories"]] == [created["id"]]


async def test_recall_filters_by_kind_and_query():
    repos, mem = FakeRepositoryPort(), FakeMemoryPort()
    await repos.save(_repo())
    svc = MemoryService(mem, repos)
    await svc.remember_repository("cyberdyne/a", content="deploy via Coolify", kind="note", author="a")
    await svc.remember_repository("cyberdyne/a", content="chose pgvector", kind="decision", author="a")
    only_decisions = await svc.recall_repository("cyberdyne/a", kind="decision")
    assert [m["content"] for m in only_decisions["memories"]] == ["chose pgvector"]
    hits = await svc.recall_repository("cyberdyne/a", query="coolify")
    assert [m["content"] for m in hits["memories"]] == ["deploy via Coolify"]


async def test_remember_unindexed_repository_rejected():
    repos, mem = FakeRepositoryPort(), FakeMemoryPort()
    await repos.save(_repo(enabled=False))
    with pytest.raises(UnknownResourceError):
        await MemoryService(mem, repos).remember_repository(
            "cyberdyne/a", content="x", kind="note", author="a")


async def test_organization_memory_and_forget():
    repos, mem = FakeRepositoryPort(), FakeMemoryPort()
    svc = MemoryService(mem, repos)
    created = await svc.remember_organization(
        "CyberdyneCorp", content="org convention", kind="convention", author="a")
    assert (await svc.recall_organization("CyberdyneCorp"))["memories"]
    assert await svc.forget(UUID(created["id"])) is True
    assert (await svc.recall_organization("CyberdyneCorp"))["memories"] == []
    assert await svc.forget(uuid4()) is False  # unknown id


async def test_recall_organization_denied_cross_org():
    """#52: a caller scoped to acme cannot recall another org's memories."""
    repos, mem = FakeRepositoryPort(), FakeMemoryPort()
    svc = MemoryService(mem, repos)
    await svc.remember_organization("victim-org", content="secret", kind="note", author="a")

    set_allowed_organizations(frozenset({"acme"}))
    try:
        with pytest.raises(UnknownResourceError):
            await svc.recall_organization("victim-org")
    finally:
        set_allowed_organizations(None)


async def test_remember_organization_denied_cross_org():
    """#53: a scoped caller cannot write into another org's namespace."""
    repos, mem = FakeRepositoryPort(), FakeMemoryPort()
    svc = MemoryService(mem, repos)

    set_allowed_organizations(frozenset({"acme"}))
    try:
        with pytest.raises(UnknownResourceError):
            await svc.remember_organization(
                "victim-org", content="x", kind="note", author="a")
    finally:
        set_allowed_organizations(None)
    # Nothing was persisted into the victim namespace.
    assert (await svc.recall_organization("victim-org"))["memories"] == []


async def test_forget_denied_cross_org_organization_memory():
    """#54: a scoped caller cannot delete another org's memory by id."""
    repos, mem = FakeRepositoryPort(), FakeMemoryPort()
    svc = MemoryService(mem, repos)
    created = await svc.remember_organization(
        "victim-org", content="secret", kind="note", author="a")

    set_allowed_organizations(frozenset({"acme"}))
    try:
        assert await svc.forget(UUID(created["id"])) is False
    finally:
        set_allowed_organizations(None)
    # The memory survived the cross-org delete attempt.
    assert (await svc.recall_organization("victim-org"))["memories"]


async def test_forget_denied_cross_org_repository_memory():
    """#54: forgetting a repo-scoped memory checks the owning repo's org scope."""
    repos, mem = FakeRepositoryPort(), FakeMemoryPort()
    await repos.save(_repo("victim-org/a"))
    svc = MemoryService(mem, repos)
    created = await svc.remember_repository(
        "victim-org/a", content="secret", kind="note", author="a")

    set_allowed_organizations(frozenset({"acme"}))
    try:
        assert await svc.forget(UUID(created["id"])) is False
    finally:
        set_allowed_organizations(None)
    assert UUID(created["id"]) in mem.items  # survived the cross-org delete attempt


async def test_same_org_caller_allowed():
    """A caller scoped to the target org retains full recall/remember/forget."""
    repos, mem = FakeRepositoryPort(), FakeMemoryPort()
    svc = MemoryService(mem, repos)

    set_allowed_organizations(frozenset({"acme"}))
    try:
        created = await svc.remember_organization(
            "acme", content="ours", kind="note", author="a")
        assert (await svc.recall_organization("acme"))["memories"]
        assert await svc.forget(UUID(created["id"])) is True
    finally:
        set_allowed_organizations(None)


async def test_unrestricted_caller_allowed_cross_org():
    """An admin/unrestricted caller (scope None) still reaches any org."""
    repos, mem = FakeRepositoryPort(), FakeMemoryPort()
    svc = MemoryService(mem, repos)
    set_allowed_organizations(None)
    created = await svc.remember_organization(
        "victim-org", content="ok", kind="note", author="a")
    assert (await svc.recall_organization("victim-org"))["memories"]
    assert await svc.forget(UUID(created["id"])) is True
