"""Documentation path detection and classification (spec: repository-sync)."""

import re

from app.domain.value_objects.enums import DocumentType

_DOC_DIRS = ("docs/", "doc/", "documentation/")
_OPENSPEC_PREFIXES = ("openspec/", "specs/", "changes/")

_ROOT_FILE_TYPES: dict[str, DocumentType] = {
    "contributing": DocumentType.CONTRIBUTING,
    "architecture": DocumentType.ARCHITECTURE,
    "security": DocumentType.SECURITY,
    "changelog": DocumentType.CHANGELOG,
    "roadmap": DocumentType.ROADMAP,
}


def is_documentation_path(path: str) -> bool:
    """Whether a repository path should be captured as documentation."""
    lower = path.lower()
    if not lower.endswith((".md", ".markdown", ".mdx")):
        return False
    name = lower.rsplit("/", 1)[-1]
    if name.startswith("readme"):
        return True
    if lower.startswith(_DOC_DIRS) or lower.startswith(_OPENSPEC_PREFIXES):
        return True
    stem = re.split(r"[.]", name)[0]
    return "/" not in lower and stem in _ROOT_FILE_TYPES


def classify_document(path: str) -> DocumentType:
    """Classify a captured documentation path (spec: docs capture)."""
    lower = path.lower()
    name = lower.rsplit("/", 1)[-1]
    stem = re.split(r"[.]", name)[0]

    if name.startswith("readme"):
        return DocumentType.README
    if lower.startswith(_OPENSPEC_PREFIXES):
        return DocumentType.OPENSPEC
    if stem in _ROOT_FILE_TYPES:
        return _ROOT_FILE_TYPES[stem]
    if lower.startswith(_DOC_DIRS):
        return DocumentType.DOCS
    return DocumentType.GENERIC_MARKDOWN


def document_title(path: str, content: str) -> str:
    """First markdown H1, else the file name."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return path.rsplit("/", 1)[-1]
