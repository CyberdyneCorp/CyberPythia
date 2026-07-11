"""Organization vulnerability view (spec: engineering-intelligence)."""

from uuid import uuid4

from app.application.use_cases.security import SecurityService
from app.domain.entities.repository import Repository
from app.domain.value_objects.enums import RepositoryVisibility
from app.domain.value_objects.full_name import RepositoryFullName
from tests.unit.application.fakes import FakeRepositoryPort


class _Metrics:
    def __init__(self):
        self.by_repo = {}

    async def get(self, repo_id):
        return self.by_repo.get(repo_id)


def _repo(name):
    return Repository(
        id=uuid4(), connection_id=uuid4(), github_id=hash(name) % 99999,
        full_name=RepositoryFullName(name), description=None,
        visibility=RepositoryVisibility.PRIVATE, default_branch="main",
        primary_language=None, archived=False, github_updated_at=None, enabled=True,
    )


async def test_lists_repos_with_alerts_most_critical_first():
    repos, metrics = FakeRepositoryPort(), _Metrics()
    a, b, clean, unknown = (
        _repo("cyberdyne/a"), _repo("cyberdyne/b"),
        _repo("cyberdyne/clean"), _repo("cyberdyne/unknown"),
    )
    for r in (a, b, clean, unknown):
        await repos.save(r)
    metrics.by_repo[a.id] = {"summary": {"vulnerabilities": {"critical": 1, "high": 3}}}
    metrics.by_repo[b.id] = {"summary": {"vulnerabilities": {"critical": 4, "high": 0}}}
    metrics.by_repo[clean.id] = {"summary": {"vulnerabilities": {"critical": 0, "high": 0}}}
    metrics.by_repo[unknown.id] = {"summary": {}}  # not captured

    out = await SecurityService(repos, metrics).organization_vulnerabilities("CyberDyne")
    # clean (0/0) and unknown (no signal) are omitted; b before a (more critical)
    assert [r["full_name"] for r in out["repositories"]] == ["cyberdyne/b", "cyberdyne/a"]
    assert out["total_critical"] == 5 and out["total_high"] == 3
