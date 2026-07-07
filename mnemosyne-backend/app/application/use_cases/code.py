"""Code search, symbol lookup, file content, and related files (spec: code-context)."""

import re
from uuid import UUID

from app.application.audit import AuditService
from app.application.errors import (
    ContentUnavailableError,
    RepositoryNotSyncedError,
    SourceNotIndexedError,
    UnknownResourceError,
)
from app.domain.entities.repository import Repository
from app.domain.ports.infra_ports import CodeChunkMatch, EmbeddingPort
from app.domain.ports.persistence_ports import (
    FilePort,
    RepositoryPort,
    SourceChunkPort,
)
from app.domain.value_objects.identity import CallerIdentity

# import/include/require targets, best-effort across languages
_IMPORT = re.compile(
    r"""^\s*(?:from\s+([\w./-]+)\s+import|import\s+([\w./-]+)|#include\s+["<]([\w./-]+)[">]"""
    r"""|(?:import|require|use)\s*\(?\s*['"]([\w./-]+)['"])""",
    re.MULTILINE,
)


class CodeUseCases:
    def __init__(
        self,
        repositories: RepositoryPort,
        files: FilePort,
        source_chunks: SourceChunkPort,
        embeddings: EmbeddingPort,
        audit: AuditService,
    ) -> None:
        self._repositories = repositories
        self._files = files
        self._chunks = source_chunks
        self._embeddings = embeddings
        self._audit = audit

    async def _code_repository(self, repository_id: UUID) -> Repository:
        repo = await self._repositories.get(repository_id)
        if repo is None:
            raise UnknownResourceError(f"repository {repository_id} not found")
        if repo.last_synced_at is None:
            raise RepositoryNotSyncedError(f"repository {repo.full_name} has not completed a sync")
        if not repo.indexing_mode.includes_source_code:
            raise SourceNotIndexedError(
                f"repository {repo.full_name} is indexed as "
                f"'{repo.indexing_mode.value}', which does not capture source code"
            )
        return repo

    async def search_code(
        self, repository_id: UUID, query: str, *, limit: int = 8
    ) -> list[CodeChunkMatch]:
        await self._code_repository(repository_id)
        return await self._embeddings.search_code(repository_id, query, limit=limit)

    async def symbols(
        self, repository_id: UUID, name: str | None = None
    ) -> list[dict[str, object]]:
        await self._code_repository(repository_id)
        if name:
            chunks = await self._chunks.get_by_symbol(repository_id, name)
        else:
            chunks = [
                c
                for c in await self._chunks.list_by_repository(repository_id)
                if c.symbol_name is not None
            ]
        return [
            {
                "symbol_name": c.symbol_name,
                "chunk_type": c.chunk_type.value,
                "file_id": str(c.file_id),
                "start_line": c.start_line,
                "end_line": c.end_line,
            }
            for c in chunks
        ]

    async def file_content(
        self, repository_id: UUID, file_id: UUID, caller: CallerIdentity | None = None
    ) -> dict[str, object]:
        await self._code_repository(repository_id)
        file = await self._files.get(file_id)
        if file is None or file.repository_id != repository_id:
            raise UnknownResourceError(f"file {file_id} not found")
        if not file.content_captured or file.content is None:
            reason = "quarantined (contained a secret)" if file.quarantined else (
                "not captured (ignored, binary, or over the size cap)"
            )
            raise ContentUnavailableError(f"content for {file.path} is unavailable: {reason}")
        await self._audit.record(caller, "code.file_content", target=file.path)
        return {
            "path": file.path,
            "language": file.language,
            "size_bytes": file.size_bytes,
            "content": file.content,
        }

    async def related_files(self, repository_id: UUID, file_id: UUID) -> dict[str, object]:
        await self._code_repository(repository_id)
        target = await self._files.get(file_id)
        if target is None or target.repository_id != repository_id:
            raise UnknownResourceError(f"file {file_id} not found")
        all_files = await self._files.list_by_repository(repository_id)
        by_stem = {_stem(f.path): f for f in all_files}

        imports_out: list[str] = []
        if target.content:
            for token in _imported_tokens(target.content):
                match = by_stem.get(_stem(token))
                if match is not None and match.path != target.path:
                    imports_out.append(match.path)

        target_stem = _stem(target.path)
        imported_by = [
            f.path
            for f in all_files
            if f.path != target.path
            and f.content
            and target_stem in {_stem(t) for t in _imported_tokens(f.content)}
        ]
        return {
            "path": target.path,
            "imports": sorted(set(imports_out)),
            "imported_by": sorted(set(imported_by)),
        }

    async def explain_structure(self, repository_id: UUID) -> dict[str, object]:
        repo = await self._repositories.get(repository_id)
        if repo is None:
            raise UnknownResourceError(f"repository {repository_id} not found")
        if repo.last_synced_at is None:
            raise RepositoryNotSyncedError(f"repository {repo.full_name} has not completed a sync")
        files = await self._files.list_by_repository(repository_id)
        languages: dict[str, int] = {}
        for f in files:
            if f.language:
                languages[f.language] = languages.get(f.language, 0) + 1
        important = [
            {"path": f.path, "kind": f.important_kind} for f in files if f.is_important
        ]
        symbols: list[dict[str, object]] = []
        if repo.indexing_mode.includes_source_code:
            for c in (await self._chunks.list_by_repository(repository_id))[:200]:
                if c.symbol_name is not None and len(symbols) < 50:
                    symbols.append(
                        {"symbol_name": c.symbol_name, "chunk_type": c.chunk_type.value}
                    )
        return {
            "full_name": str(repo.full_name),
            "primary_language": repo.primary_language,
            "file_count": len(files),
            "languages": dict(sorted(languages.items(), key=lambda kv: -kv[1])),
            "important_files": important[:50],
            "key_symbols": symbols,
        }


def _stem(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    return name.split(".", 1)[0].lower()


def _imported_tokens(content: str) -> list[str]:
    tokens: list[str] = []
    for match in _IMPORT.finditer(content):
        token = next((g for g in match.groups() if g), None)
        if token:
            tokens.append(token.rsplit("/", 1)[-1].rsplit(".", 1)[-1])
    return tokens
