"""OpenSpec content detection and parsing (spec: repository-sync).

Works over a repository file listing plus a content loader, so the
service stays pure: callers supply paths and fetched content.
"""

import hashlib
import re
from dataclasses import dataclass, field

_CHANGE_ROOTS = ("openspec/changes/", "changes/")
_ARCHIVE_MARKER = "/archive/"
_ARCHIVED_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}-")


@dataclass(slots=True)
class ParsedOpenSpecChange:
    change_id: str
    path: str  # change folder path
    status: str  # active | archived | unknown
    proposal: str | None = None
    design: str | None = None
    tasks: str | None = None
    affected_specs: list[str] = field(default_factory=list)

    @property
    def content_hash(self) -> str:
        joined = "\x00".join(
            [self.proposal or "", self.design or "", self.tasks or ""]
        )
        return hashlib.sha256(joined.encode()).hexdigest()


def find_change_folders(paths: list[str]) -> dict[str, str]:
    """Map change folder path -> change id, from a repository file listing."""
    folders: dict[str, str] = {}
    for path in paths:
        for root in _CHANGE_ROOTS:
            if not path.startswith(root):
                continue
            remainder = path.removeprefix(root)
            if _ARCHIVE_MARKER.strip("/") == remainder.split("/", 1)[0]:
                # openspec/changes/archive/YYYY-MM-DD-name/...
                parts = remainder.split("/")
                if len(parts) >= 2:
                    folders[f"{root}archive/{parts[1]}"] = parts[1]
            else:
                change_id = remainder.split("/", 1)[0]
                if "/" in remainder and change_id:
                    folders[f"{root}{change_id}"] = change_id
            break
    return folders


def _infer_status(folder: str) -> str:
    if _ARCHIVE_MARKER in f"/{folder}/":
        return "archived"
    if _ARCHIVED_PREFIX.match(folder.rsplit("/", 1)[-1]):
        return "archived"
    return "active"


def _extract_affected_specs(paths: list[str], folder: str) -> list[str]:
    specs = set()
    prefix = f"{folder}/specs/"
    for path in paths:
        if path.startswith(prefix):
            remainder = path.removeprefix(prefix)
            if "/" in remainder:
                specs.add(remainder.split("/", 1)[0])
    return sorted(specs)


def parse_change(
    folder: str,
    change_id: str,
    paths: list[str],
    contents: dict[str, str],
) -> ParsedOpenSpecChange:
    """Assemble a change from its folder path and pre-fetched file contents.

    ``contents`` maps repository paths to file text; the caller fetches
    only ``interesting_files(folder)`` paths.
    """
    normalized_id = _ARCHIVED_PREFIX.sub("", change_id)
    return ParsedOpenSpecChange(
        change_id=normalized_id,
        path=folder,
        status=_infer_status(folder),
        proposal=contents.get(f"{folder}/proposal.md"),
        design=contents.get(f"{folder}/design.md"),
        tasks=contents.get(f"{folder}/tasks.md"),
        affected_specs=_extract_affected_specs(paths, folder),
    )


def interesting_files(folder: str) -> list[str]:
    return [f"{folder}/proposal.md", f"{folder}/design.md", f"{folder}/tasks.md"]
