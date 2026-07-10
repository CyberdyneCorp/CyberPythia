"""Project readiness classification (spec: engineering-intelligence).

Maps observable repository signals to Amini's phase gates — MVP (Alpha),
READY (Beta), DONE (GA). Pure: signal inputs in, a gate + per-check breakdown out.

Only GitHub-observable signals decide the gate ("observable-only, strict"). Each
check is ``met`` / ``missing`` / ``unknown`` (unknown = the signal isn't captured in
the repository's indexing mode, e.g. CI when no file tree is indexed) — unknown
never counts as met.
"""

from dataclasses import dataclass
from typing import Any

_BUG_RATIO_MAX = 0.25  # DONE: open bugs must be < 25% of open issues


@dataclass(slots=True)
class ReadinessInputs:
    has_readme: bool | None = None
    has_guide_doc: bool | None = None  # a DOCS-type document
    has_adr: bool | None = None  # ARCHITECTURE-type document
    has_security_doc: bool | None = None  # SECURITY-type document
    has_openspec: bool | None = None
    has_ci: bool | None = None
    has_tests: bool | None = None
    has_dependency_manifest: bool | None = None
    has_dependabot: bool | None = None
    has_security_scanning: bool | None = None
    has_releases: bool | None = None
    closed_issues: int = 0
    merged_prs: int = 0
    open_issues: int = 0
    open_bugs: int = 0


def _status(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return "met" if value else "missing"


def classify_readiness(inp: ReadinessInputs) -> dict[str, Any]:
    low_bug_ratio = (inp.open_bugs / inp.open_issues < _BUG_RATIO_MAX) if inp.open_issues else True

    ready = {
        "ci": inp.has_ci,
        "tests": inp.has_tests,
        "documented_design": (inp.has_openspec or inp.has_adr) or None
        if inp.has_openspec is None and inp.has_adr is None
        else bool(inp.has_openspec or inp.has_adr),
        "closed_issues": inp.closed_issues > 0,
        "merged_prs": inp.merged_prs > 0,
        "readme": inp.has_readme,
        "guide_docs": inp.has_guide_doc,
    }
    done = {
        "dependency_manifest": inp.has_dependency_manifest,
        "monitoring": (inp.has_dependabot or inp.has_security_scanning) or None
        if inp.has_dependabot is None and inp.has_security_scanning is None
        else bool(inp.has_dependabot or inp.has_security_scanning),
        "security_doc": inp.has_security_doc,
        "low_bug_ratio": low_bug_ratio,
        "releases": inp.has_releases,
    }

    is_ready = all(v is True for v in ready.values())
    is_done = is_ready and all(v is True for v in done.values())
    gate = "DONE" if is_done else "READY" if is_ready else "MVP"

    return {
        "gate": gate,
        "ready_checks": {k: _status(v) for k, v in ready.items()},
        "done_checks": {k: _status(v) for k, v in done.items()},
        "missing_for_ready": [k for k, v in ready.items() if v is not True],
        "missing_for_done": [k for k, v in {**ready, **done}.items() if v is not True],
    }
