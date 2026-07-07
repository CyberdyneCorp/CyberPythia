"""Semantic search, context packs, and repository Q&A (spec: context-packs)."""

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from app.application.errors import RepositoryNotSyncedError, UnknownResourceError
from app.domain.entities.context_pack import (
    ContextPack,
    DocRef,
    FileRef,
    IssueRef,
    OpenSpecRef,
    PullRequestRef,
)
from app.domain.entities.repository import Repository
from app.domain.ports.infra_ports import AnswerPort, ChunkMatch, EmbeddingPort
from app.domain.ports.persistence_ports import (
    ContextPackPort,
    DocumentPort,
    FilePort,
    IssuePort,
    OpenSpecPort,
    PullRequestPort,
    RepositoryPort,
)
from app.domain.services.relevance import keyword_score

MIN_SCORE = 0.15
TOP_N = 8

INSUFFICIENT_CONTEXT_MESSAGE = (
    "The indexed context does not cover this question. "
    "Indexed content types for this repository: {types}."
)


class ContextUseCases:
    def __init__(
        self,
        repositories: RepositoryPort,
        documents: DocumentPort,
        openspec: OpenSpecPort,
        issues: IssuePort,
        pull_requests: PullRequestPort,
        files: FilePort,
        context_packs: ContextPackPort,
        embeddings: EmbeddingPort,
        answerer: AnswerPort,
        metrics_store: object,
    ) -> None:
        self._repositories = repositories
        self._documents = documents
        self._openspec = openspec
        self._issues = issues
        self._pull_requests = pull_requests
        self._files = files
        self._context_packs = context_packs
        self._embeddings = embeddings
        self._answerer = answerer
        self._metrics_store = metrics_store

    async def _synced_repository(self, repository_id: UUID) -> Repository:
        repository = await self._repositories.get(repository_id)
        if repository is None:
            raise UnknownResourceError(f"repository {repository_id} not found")
        if repository.last_synced_at is None:
            raise RepositoryNotSyncedError(
                f"repository {repository.full_name} has never completed a sync"
            )
        return repository

    async def search_docs(
        self, repository_id: UUID, query: str, *, limit: int = TOP_N
    ) -> list[ChunkMatch]:
        await self._synced_repository(repository_id)
        return await self._embeddings.search(repository_id, query, limit=limit)

    async def build_context_pack(self, repository_id: UUID, query: str) -> ContextPack:
        repository = await self._synced_repository(repository_id)
        mode = repository.indexing_mode
        sync_ts = repository.last_synced_at.isoformat() if repository.last_synced_at else ""

        cached = await self._context_packs.find_cached(
            repository_id, query, mode.value, sync_ts
        )
        if cached is not None:
            return cached

        doc_matches = await self._embeddings.search(repository_id, query, limit=TOP_N)
        seen_paths: set[str] = set()
        relevant_docs = []
        for match in doc_matches:
            if match.path in seen_paths:
                continue
            seen_paths.add(match.path)
            relevant_docs.append(
                DocRef(
                    path=match.path,
                    title=match.title,
                    doc_type=match.doc_type,
                    score=round(match.score, 4),
                    excerpt=match.excerpt,
                )
            )

        openspec_changes = await self._openspec.list_by_repository(repository_id)
        relevant_openspec = _top(
            [
                OpenSpecRef(
                    change_id=c.change_id,
                    path=c.path,
                    status=c.status.value,
                    score=round(
                        keyword_score(
                            query, c.change_id.replace("-", " "), c.proposal, c.tasks,
                            weights=(2.0, 1.0, 0.5),
                        ),
                        4,
                    ),
                )
                for c in openspec_changes
            ]
        )

        excluded: list[str] = []
        relevant_issues: list[IssueRef] = []
        relevant_prs: list[PullRequestRef] = []
        if mode.includes_issues_and_prs:
            issues = await self._issues.list_by_repository(repository_id)
            relevant_issues = _top(
                [
                    IssueRef(
                        number=i.number,
                        title=i.title,
                        state=i.state.value,
                        score=round(
                            keyword_score(
                                query, i.title, i.body, " ".join(i.labels),
                                weights=(2.0, 1.0, 1.0),
                            ),
                            4,
                        ),
                    )
                    for i in issues
                ]
            )
            prs = await self._pull_requests.list_by_repository(repository_id)
            relevant_prs = _top(
                [
                    PullRequestRef(
                        number=p.number,
                        title=p.title,
                        state=p.state.value,
                        score=round(
                            keyword_score(query, p.title, p.body, weights=(2.0, 1.0)), 4
                        ),
                    )
                    for p in prs
                ]
            )
        else:
            excluded.append("issues")
            excluded.append("pull_requests")

        relevant_files: list[FileRef] = []
        if mode.includes_file_tree:
            files = await self._files.list_by_repository(repository_id)
            relevant_files = _top(
                [
                    FileRef(
                        path=f.path,
                        kind=f.important_kind,
                        score=round(
                            keyword_score(query, f.path.replace("/", " ").replace("_", " "))
                            + (0.1 if f.is_important else 0.0),
                            4,
                        ),
                    )
                    for f in files
                    if not f.is_binary
                ]
            )
        else:
            excluded.append("files")

        pack = ContextPack(
            id=uuid4(),
            repository_id=repository_id,
            query=query,
            mode=mode,
            repository_summary=await self._summary_text(repository),
            relevant_docs=relevant_docs,
            relevant_openspec_changes=relevant_openspec,
            relevant_issues=relevant_issues,
            relevant_pull_requests=relevant_prs,
            relevant_files=relevant_files,
            risks=_derive_risks(relevant_docs, relevant_openspec, excluded),
            suggested_next_steps=_derive_next_steps(relevant_docs, relevant_openspec),
            excluded_categories=excluded,
            sync_timestamp=repository.last_synced_at,
            created_at=datetime.now(UTC),
        )
        await self._context_packs.save(pack)
        return pack

    async def ask(self, repository_id: UUID, question: str) -> dict[str, object]:
        """Grounded answer with citations; refuses rather than fabricates (spec)."""
        repository = await self._synced_repository(repository_id)
        matches = await self._embeddings.search(repository_id, question, limit=TOP_N)
        strong = [m for m in matches if m.score >= MIN_SCORE]
        if not strong:
            indexed = ["documentation", "openspec"]
            if repository.indexing_mode.includes_issues_and_prs:
                indexed += ["issues", "pull_requests"]
            if repository.indexing_mode.includes_file_tree:
                indexed += ["file_tree"]
            return {
                "answer": INSUFFICIENT_CONTEXT_MESSAGE.format(types=", ".join(indexed)),
                "sources": [],
                "grounded": False,
            }
        blocks = [f"[{m.path}] {m.excerpt}" for m in strong]
        answer = await self._answerer.answer(question, blocks)
        return {
            "answer": answer,
            "sources": [
                {"path": m.path, "title": m.title, "score": round(m.score, 4)} for m in strong
            ],
            "grounded": True,
        }

    async def _summary_text(self, repository: Repository) -> str:
        stored = await self._metrics_store.get(repository.id)  # type: ignore[attr-defined]
        parts = [
            f"{repository.full_name}: {repository.description or 'no description'}.",
            f"Primary language: {repository.primary_language or 'unknown'}.",
            f"Indexing mode: {repository.indexing_mode.value}.",
        ]
        if stored:
            s = stored["summary"]
            parts.append(
                f"Docs: {s.get('documents', 0)} (README: {s.get('has_readme')}, "
                f"OpenSpec changes: {s.get('openspec_changes', 0)}). "
                f"Issues open/closed: {s.get('open_issues', 0)}/{s.get('closed_issues', 0)}. "
                f"PRs open/merged: {s.get('open_prs', 0)}/{s.get('merged_prs', 0)}."
            )
        return " ".join(parts)


class _Scored(Protocol):
    @property
    def score(self) -> float: ...


def _top[R: _Scored](refs: list[R], *, n: int = TOP_N, min_score: float = MIN_SCORE) -> list[R]:
    return sorted(
        (r for r in refs if r.score >= min_score), key=lambda r: -r.score
    )[:n]


def _derive_risks(
    docs: list[DocRef], openspec_changes: list[OpenSpecRef], excluded: list[str]
) -> list[str]:
    risks = []
    if not docs:
        risks.append("No relevant documentation found for this task.")
    active = [c for c in openspec_changes if c.status == "active"]
    if active:
        risks.append(
            "Active OpenSpec changes may overlap with this task: "
            + ", ".join(c.change_id for c in active[:3])
        )
    if excluded:
        risks.append(
            "Content not indexed in this mode: " + ", ".join(sorted(set(excluded)))
        )
    return risks


def _derive_next_steps(docs: list[DocRef], openspec_changes: list[OpenSpecRef]) -> list[str]:
    steps = []
    if docs:
        steps.append(f"Read {docs[0].path} first.")
    if openspec_changes:
        steps.append(f"Review OpenSpec change '{openspec_changes[0].change_id}'.")
    steps.append("Request full content of the referenced items before implementing.")
    return steps
