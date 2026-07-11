"""In-memory fakes for application-layer unit tests."""

from datetime import UTC, datetime
from uuid import UUID

from app.domain.entities.github_connection import GitHubConnection
from app.domain.ports.github_port import (
    GitHubAuthError,
    GitHubFileData,
    GitHubIssueData,
    GitHubPullRequestData,
    GitHubRepoData,
    GitHubTokenInfo,
)

NOW = datetime(2026, 7, 7, 12, 0, tzinfo=UTC)


class FakeCipher:
    def encrypt(self, plaintext: str) -> bytes:
        return f"enc:{plaintext}".encode()

    def decrypt(self, ciphertext: bytes) -> str:
        return ciphertext.decode().removeprefix("enc:")


class FakeGitHubAppAuth:
    def __init__(self):
        self.fails = False
        self.calls = 0

    async def installation_token(self, app_id, installation_id, private_key_pem):
        from app.domain.ports.github_app_port import GitHubAppError

        self.calls += 1
        if self.fails:
            raise GitHubAppError("bad app credentials")
        return f"ghs_inst_{installation_id}"

    async def convert_manifest_code(self, code):
        from app.domain.ports.github_app_port import (
            AppManifestCredentials,
            GitHubAppError,
        )

        if self.fails:
            raise GitHubAppError("manifest conversion failed")
        return AppManifestCredentials(
            app_id="424242", private_key_pem="-----BEGIN PRIVATE KEY-----\nk\n-----END",
            webhook_secret="whsec", owner_login="cyberdyne",
            html_url="https://github.com/apps/mnemosyne-cyberdyne", slug="mnemosyne-cyberdyne",
        )


class FakeConnectionPort:
    def __init__(self):
        self.items: dict[UUID, GitHubConnection] = {}

    async def save(self, connection):
        self.items[connection.id] = connection

    async def get(self, connection_id):
        return self.items.get(connection_id)

    async def get_by_owner(self, owner):
        return next((c for c in self.items.values() if c.owner == owner), None)

    async def list_all(self):
        return sorted(self.items.values(), key=lambda c: c.owner)

    async def delete(self, connection_id):
        self.items.pop(connection_id, None)


class FakeRepositoryPort:
    def __init__(self):
        self.items = {}

    async def save(self, repository):
        self.items[repository.id] = repository

    async def save_many(self, repositories):
        for r in repositories:
            existing = next(
                (e for e in self.items.values() if e.github_id == r.github_id), None
            )
            if existing is not None:
                r.id = existing.id
            self.items[r.id] = r

    async def get(self, repository_id):
        return self.items.get(repository_id)

    async def get_by_full_name(self, full_name):
        return next((r for r in self.items.values() if str(r.full_name) == full_name), None)

    async def list_all(self, *, enabled_only=False):
        repos = sorted(self.items.values(), key=lambda r: str(r.full_name))
        return [r for r in repos if r.enabled] if enabled_only else repos


class FakeDocumentPort:
    def __init__(self):
        self.items = {}

    async def save(self, document):
        key = (document.repository_id, document.path)
        existing = self.items.get(key)
        if existing is not None:
            document.id = existing.id
        self.items[key] = document

    async def get(self, document_id):
        return next((d for d in self.items.values() if d.id == document_id), None)

    async def get_by_path(self, repository_id, path):
        return self.items.get((repository_id, path))

    async def list_by_repository(self, repository_id):
        return sorted(
            (d for (rid, _), d in self.items.items() if rid == repository_id),
            key=lambda d: d.path,
        )

    async def delete_missing(self, repository_id, seen_paths):
        stale = [
            k for k in self.items if k[0] == repository_id and k[1] not in seen_paths
        ]
        for k in stale:
            del self.items[k]
        return len(stale)


class FakeOpenSpecPort:
    def __init__(self):
        self.items = {}

    async def save(self, change):
        key = (change.repository_id, change.change_id)
        existing = self.items.get(key)
        if existing is not None:
            change.id = existing.id
        self.items[key] = change

    async def list_by_repository(self, repository_id):
        return sorted(
            (c for (rid, _), c in self.items.items() if rid == repository_id),
            key=lambda c: c.change_id,
        )


class FakeIssuePort:
    def __init__(self):
        self.items = {}

    async def save_many(self, issues):
        for issue in issues:
            key = (issue.repository_id, issue.number)
            existing = self.items.get(key)
            if existing is not None:
                issue.id = existing.id
            self.items[key] = issue

    async def get_by_number(self, repository_id, number):
        return self.items.get((repository_id, number))

    async def list_by_repository(self, repository_id, *, state=None, label=None):
        issues = [i for (rid, _), i in self.items.items() if rid == repository_id]
        if state:
            issues = [i for i in issues if i.state.value == state]
        if label:
            issues = [i for i in issues if label in i.labels]
        return sorted(issues, key=lambda i: -i.number)


class FakePullRequestPort:
    def __init__(self):
        self.items = {}

    async def save_many(self, pull_requests):
        for pr in pull_requests:
            key = (pr.repository_id, pr.number)
            existing = self.items.get(key)
            if existing is not None:
                pr.id = existing.id
            self.items[key] = pr

    async def get_by_number(self, repository_id, number):
        return self.items.get((repository_id, number))

    async def list_by_repository(self, repository_id, *, state=None, author=None):
        prs = [p for (rid, _), p in self.items.items() if rid == repository_id]
        if state:
            prs = [p for p in prs if p.state.value == state]
        if author:
            prs = [p for p in prs if p.author == author]
        return sorted(prs, key=lambda p: -p.number)


class FakeFilePort:
    def __init__(self):
        self.trees = {}

    async def replace_tree(self, repository_id, files):
        # Preserve id + content for unchanged files (same path + sha), mirroring
        # the Postgres adapter so re-syncs keep captured content and chunks.
        prior = {f.path: f for f in self.trees.get(repository_id, [])}
        reconciled = []
        for f in files:
            existing = prior.get(f.path)
            if existing is not None and existing.sha == f.sha:
                f.id = existing.id
                f.content = existing.content
                f.content_captured = existing.content_captured
                f.content_hash = existing.content_hash
                f.quarantined = existing.quarantined
            reconciled.append(f)
        self.trees[repository_id] = reconciled

    async def list_by_repository(self, repository_id):
        return sorted(self.trees.get(repository_id, []), key=lambda f: f.path)

    async def get(self, file_id):
        for files in self.trees.values():
            for f in files:
                if f.id == file_id:
                    return f
        return None

    async def get_by_path(self, repository_id, path):
        return next(
            (f for f in self.trees.get(repository_id, []) if f.path == path), None
        )

    async def save_content(self, file):
        for files in self.trees.values():
            for i, f in enumerate(files):
                if f.id == file.id:
                    files[i] = file
                    return


class FakeSourceChunkPort:
    def __init__(self):
        self.by_file = {}

    async def replace_for_file(self, file_id, chunks):
        self.by_file[file_id] = list(chunks)

    async def delete_for_file(self, file_id):
        self.by_file.pop(file_id, None)

    async def list_by_repository(self, repository_id):
        out = [
            c
            for chunks in self.by_file.values()
            for c in chunks
            if c.repository_id == repository_id
        ]
        return sorted(out, key=lambda c: c.start_line)

    async def get_by_symbol(self, repository_id, symbol_name):
        return [
            c
            for c in await self.list_by_repository(repository_id)
            if c.symbol_name == symbol_name
        ]


class FakeSyncJobPort:
    def __init__(self):
        self.items = {}

    async def save(self, job):
        self.items[job.id] = job

    async def get(self, job_id):
        return self.items.get(job_id)

    async def get_latest(self, repository_id):
        jobs = [j for j in self.items.values() if j.repository_id == repository_id]
        return max(jobs, key=lambda j: j.started_at or NOW, default=None)

    async def list_recent(self, limit=50):
        jobs = sorted(self.items.values(), key=lambda j: j.started_at or NOW, reverse=True)
        return jobs[:limit]


class FakeOrganizationPort:
    def __init__(self):
        self.orgs = {}  # login -> sync_enabled

    async def upsert_many(self, logins, *, default_enabled):
        for login in logins:
            self.orgs.setdefault(login, default_enabled)

    async def list_all(self):
        from app.domain.entities.organization import Organization

        return [
            Organization(login=k, sync_enabled=v)
            for k, v in sorted(self.orgs.items())
        ]

    async def set_enabled(self, login, *, enabled):
        from app.domain.entities.organization import Organization

        if login not in self.orgs:
            return None
        self.orgs[login] = enabled
        return Organization(login=login, sync_enabled=enabled)

    async def disabled_logins(self):
        return {k for k, v in self.orgs.items() if not v}


class FakeSyncRunPort:
    def __init__(self):
        self.runs = []

    async def record(self, run):
        self.runs.append(run)

    async def list_recent(self, limit=50):
        return sorted(self.runs, key=lambda r: r.finished_at, reverse=True)[:limit]


class FakeSyncLock:
    def __init__(self):
        self.locked = set()

    async def acquire(self, repository_id):
        if repository_id in self.locked:
            return False
        self.locked.add(repository_id)
        return True

    async def release(self, repository_id):
        self.locked.discard(repository_id)

    async def is_locked(self, repository_id):
        return repository_id in self.locked


class FakeQueue:
    def __init__(self):
        self.jobs = []

    async def enqueue(self, job_name, payload, *, defer_seconds=0.0):
        self.jobs.append((job_name, payload, defer_seconds))


class FakeMemoryPort:
    def __init__(self):
        self.items = {}  # id -> AgentMemory

    async def save(self, memory):
        self.items[memory.id] = memory

    async def get(self, memory_id):
        return self.items.get(memory_id)

    def _filter(self, rows, kind, query, limit):
        if kind:
            rows = [m for m in rows if m.kind == kind]
        if query:
            rows = [m for m in rows if query.lower() in m.content.lower()]
        rows = sorted(rows, key=lambda m: m.created_at, reverse=True)
        return rows[:limit]

    async def list_for_repository(self, repository_id, *, kind=None, query=None, limit=50):
        rows = [m for m in self.items.values() if m.repository_id == repository_id]
        return self._filter(rows, kind, query, limit)

    async def list_for_organization(self, organization, *, kind=None, query=None, limit=50):
        rows = [m for m in self.items.values() if m.organization == organization]
        return self._filter(rows, kind, query, limit)

    async def delete(self, memory_id):
        return self.items.pop(memory_id, None) is not None


class FakeReadinessHistory:
    def __init__(self):
        self.rows = {}  # repo_id -> {captured_on: snapshot}

    async def record(self, snapshot):
        self.rows.setdefault(snapshot.repository_id, {})[snapshot.captured_on] = snapshot

    async def list_for_repository(self, repository_id, *, limit=180):
        return sorted(
            self.rows.get(repository_id, {}).values(), key=lambda s: s.captured_on
        )[:limit]

    async def all_by_repository(self):
        return {rid: await self.list_for_repository(rid) for rid in self.rows}


class FakeStorage:
    def __init__(self):
        self.objects = {}

    async def put_json(self, key, payload):
        self.objects[key] = payload

    async def get_json(self, key):
        return self.objects[key]


class FakeGitHub:
    """Scriptable GitHubPort fake."""

    def __init__(self):
        self.token_info = GitHubTokenInfo(
            login="cyberdyne",
            owner_type="Organization",
            permissions={"contents", "issues", "pull_requests", "metadata"},
        )
        self.repos: list[GitHubRepoData] = []
        self.installation_repos: list[GitHubRepoData] | None = None  # App discovery path
        self.files: dict[str, str] = {}  # path -> content
        self.tree: list[GitHubFileData] = []
        self.issues: list[GitHubIssueData] = []
        self.releases_present = False
        self.vuln_summary = None  # None = unknown/not permitted
        self.pull_requests: list[GitHubPullRequestData] = []
        self.auth_fails = False
        self.rate_limit = {"limit": 5000, "remaining": 4999}

    async def validate_token(self, token):
        if self.auth_fails:
            raise GitHubAuthError("bad token")
        return self.token_info

    async def validate_installation_token(self, token, owner=""):
        if self.auth_fails:
            raise GitHubAuthError("bad token")
        if owner:
            return GitHubTokenInfo(
                login=owner,
                owner_type="Organization",
                permissions=set(self.token_info.permissions),
            )
        return self.token_info

    async def list_repositories(self, token):
        return self.repos

    async def list_installation_repositories(self, token):
        return self.installation_repos if self.installation_repos is not None else self.repos

    async def get_repository(self, token, full_name):
        return next(r for r in self.repos if r.full_name == full_name)

    async def get_file_content(self, token, full_name, path):
        return self.files[path]

    async def get_tree(self, token, full_name, branch):
        return self.tree

    async def has_releases(self, token, full_name):
        return self.releases_present

    async def vulnerability_summary(self, token, full_name):
        return self.vuln_summary

    async def list_issues(self, token, full_name):
        return self.issues

    async def get_issue(self, token, full_name, number):
        from app.domain.ports.github_port import GitHubNotFoundError

        match = next((i for i in self.issues if i.number == number), None)
        if match is None:
            raise GitHubNotFoundError(f"issue {number}")
        return match

    async def list_pull_requests(self, token, full_name):
        return self.pull_requests

    async def get_pull_request(self, token, full_name, number):
        from app.domain.ports.github_port import GitHubNotFoundError

        match = next((p for p in self.pull_requests if p.number == number), None)
        if match is None:
            raise GitHubNotFoundError(f"pr {number}")
        return match

    async def get_rate_limit(self, token):
        if self.auth_fails:
            raise GitHubAuthError("bad token")
        return self.rate_limit
