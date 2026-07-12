"""Global semantic search respects the caller's org scope (spec: auth)."""

from uuid import uuid4

from app.application.use_cases.cross_repo import CrossRepoService
from app.domain.entities.repository import Repository
from app.domain.services.org_scope import set_allowed_organizations
from app.domain.value_objects.enums import RepositoryVisibility
from app.domain.value_objects.full_name import RepositoryFullName
from tests.unit.application.fakes import (
    FakeIssuePort,
    FakePullRequestPort,
    FakeRepositoryPort,
)


class _RecordingEmbeddings:
    def __init__(self):
        self.repo_ids_seen = []

    async def search_global(self, query, *, repository_ids=None, limit=8):
        self.repo_ids_seen.append(repository_ids)
        return []

    async def search_code_global(self, query, *, repository_ids=None, limit=8):
        self.repo_ids_seen.append(repository_ids)
        return []


def _repo(full_name, enabled=True):
    return Repository(
        id=uuid4(), connection_id=uuid4(), github_id=hash(full_name) % 99999,
        full_name=RepositoryFullName(full_name), description=None,
        visibility=RepositoryVisibility.PRIVATE, default_branch="main",
        primary_language=None, archived=False, github_updated_at=None, enabled=enabled,
    )


async def test_global_search_bounded_to_caller_org_scope():
    repos = FakeRepositoryPort()
    cyber, amini = _repo("cyberdyne/a"), _repo("aminitech/x")
    await repos.save(cyber)
    await repos.save(amini)
    emb = _RecordingEmbeddings()
    svc = CrossRepoService(repos, FakeIssuePort(), FakePullRequestPort(), emb)

    set_allowed_organizations(frozenset({"cyberdyne"}))
    try:
        await svc.search("q", kind="docs")  # NB: no organization filter
    finally:
        set_allowed_organizations(None)

    # A scoped caller must NOT get an unbounded (None) global search.
    passed = emb.repo_ids_seen[0]
    assert passed is not None
    assert set(passed) == {cyber.id}  # only the in-scope repo


async def test_global_search_unrestricted_when_unscoped():
    repos = FakeRepositoryPort()
    await repos.save(_repo("cyberdyne/a"))
    emb = _RecordingEmbeddings()
    svc = CrossRepoService(repos, FakeIssuePort(), FakePullRequestPort(), emb)
    set_allowed_organizations(None)  # admin / bare entitlement
    await svc.search("q", kind="code")
    assert emb.repo_ids_seen[0] is None  # search all indexed repos
