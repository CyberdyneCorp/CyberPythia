"""Detect presence signals from a repository's captured file tree.

Pure: file paths in, ``RepositorySignals`` out. When the indexing mode captures
no tree, every signal is ``None`` (unknown) — never ``False`` (spec:
engineering-intelligence, absent-not-zero).
"""

import re

from app.domain.value_objects.enums import IndexingMode
from app.domain.value_objects.health import RepositorySignals

_CI_PATHS = (
    ".gitlab-ci.yml",
    ".circleci/config.yml",
    "azure-pipelines.yml",
    "jenkinsfile",
)
_MANIFESTS = (
    "package.json",
    "pyproject.toml",
    "go.mod",
    "cargo.toml",
    "pom.xml",
    "build.gradle",
    "gemfile",
)
_TEST_FILE = re.compile(r"(^|/)(test_[^/]+|[^/]+_test|[^/]+\.(spec|test))\.[^/]+$")
_TEST_DIR = re.compile(r"(^|/)(tests?|__tests__)/")


def _has_ci(paths: list[str]) -> bool:
    return any(
        (p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml"))) or p in _CI_PATHS
        for p in paths
    )


def _has_tests(paths: list[str]) -> bool:
    return any(_TEST_DIR.search(p) or _TEST_FILE.search(p) for p in paths)


def _has_manifest(paths: list[str]) -> bool:
    return any(
        p in _MANIFESTS or (p.startswith("requirements") and p.endswith(".txt")) for p in paths
    )


def _has_dependabot(paths: list[str]) -> bool:
    return any(p in (".github/dependabot.yml", ".github/dependabot.yaml") for p in paths)


def _has_security_scanning(paths: list[str]) -> bool:
    # CodeQL / Semgrep / Trivy / Snyk workflows under .github/workflows
    return any(
        p.startswith(".github/workflows/")
        and any(t in p for t in ("codeql", "semgrep", "trivy", "snyk", "security"))
        for p in paths
    )


def _basename_startswith(paths: list[str], prefix: str) -> bool:
    return any(p.rsplit("/", 1)[-1].startswith(prefix) for p in paths)


class RepositorySignalsService:
    """Derive CI/tests/manifest/contributing/license presence from file paths."""

    def detect(self, paths: list[str], mode: IndexingMode) -> RepositorySignals:
        if not mode.includes_file_tree:
            return RepositorySignals()  # all unknown
        lowered = [p.lower() for p in paths]
        return RepositorySignals(
            has_ci=_has_ci(lowered),
            has_tests=_has_tests(lowered),
            has_dependency_manifest=_has_manifest(lowered),
            has_contributing=_basename_startswith(lowered, "contributing"),
            has_license=_basename_startswith(lowered, "license"),
            has_dependabot=_has_dependabot(lowered),
            has_security_scanning=_has_security_scanning(lowered),
        )
