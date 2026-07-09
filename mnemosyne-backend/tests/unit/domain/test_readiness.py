"""Unit tests for the readiness classifier (spec: engineering-intelligence)."""

from app.domain.services.readiness import ReadinessInputs, classify_readiness


def _ready_inputs(**over) -> ReadinessInputs:
    base = dict(
        has_readme=True, has_guide_doc=True, has_adr=True, has_openspec=True,
        has_ci=True, has_tests=True, closed_issues=3, merged_prs=5,
    )
    base.update(over)
    return ReadinessInputs(**base)  # type: ignore[arg-type]


def _done_inputs(**over) -> ReadinessInputs:
    base = dict(
        has_dependency_manifest=True, has_dependabot=True, has_security_doc=True,
        open_issues=10, open_bugs=1,
    )
    return _ready_inputs(**{**base, **over})


def test_bare_repo_is_mvp():
    r = classify_readiness(ReadinessInputs(has_readme=True))
    assert r["gate"] == "MVP"
    assert "ci" in r["missing_for_ready"]


def test_ready_when_all_ready_checks_met():
    r = classify_readiness(_ready_inputs())
    assert r["gate"] == "READY"
    assert r["missing_for_ready"] == []
    assert r["ready_checks"]["ci"] == "met"


def test_done_when_hardening_met():
    r = classify_readiness(_done_inputs())
    assert r["gate"] == "DONE"
    assert r["missing_for_done"] == []


def test_unknown_ci_blocks_ready_and_is_flagged():
    # file tree not indexed → has_ci/has_tests None → cannot be READY
    r = classify_readiness(_ready_inputs(has_ci=None, has_tests=None))
    assert r["gate"] == "MVP"
    assert r["ready_checks"]["ci"] == "unknown"
    assert r["ready_checks"]["tests"] == "unknown"


def test_no_closed_issues_blocks_ready():
    r = classify_readiness(_ready_inputs(closed_issues=0))
    assert r["gate"] == "MVP"
    assert "closed_issues" in r["missing_for_ready"]


def test_high_bug_ratio_blocks_done():
    r = classify_readiness(_done_inputs(open_issues=4, open_bugs=3))  # 75% bugs
    assert r["gate"] == "READY"
    assert "low_bug_ratio" in r["missing_for_done"]


def test_missing_monitoring_blocks_done():
    r = classify_readiness(_done_inputs(has_dependabot=False, has_security_scanning=False))
    assert r["gate"] == "READY"
    assert "monitoring" in r["missing_for_done"]
