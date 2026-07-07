"""Repository health scoring (spec: engineering-intelligence).

Pure: ``HealthInputs`` in, ``RepositoryHealth`` out. Each component is 0-100 or
``None`` (inputs absent/unknown); the overall is the weight-renormalised mean of
the present components. Every component reports its inputs, and lost points are
explained by ranked findings.
"""

from datetime import datetime

from app.domain.value_objects.health import (
    ComponentScore,
    HealthFinding,
    HealthInputs,
    RepositoryHealth,
    Severity,
    grade_for,
)

_DAY = 86400.0

# Component weights (documented constants). None components drop out and the
# remaining weights renormalise.
_WEIGHTS = {
    "documentation": 0.25,
    "delivery": 0.25,
    "maintenance": 0.20,
    "testing_ci": 0.15,
    "activity": 0.15,
}


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def _decay(value: float | None, best_days: float, worst_days: float) -> float | None:
    """100 at/under ``best_days`` seconds, 0 at/over ``worst_days``, linear between."""
    if value is None:
        return None
    days = value / _DAY
    if days <= best_days:
        return 100.0
    if days >= worst_days:
        return 0.0
    return _clamp(100.0 * (worst_days - days) / (worst_days - best_days))


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _documentation(inp: HealthInputs) -> ComponentScore:
    score = None
    if inp.synced:
        score = (40 if inp.has_readme else 0) + (30 if inp.has_docs else 0) + (
            30 if inp.has_openspec else 0
        )
    return ComponentScore(
        name="documentation",
        weight=_WEIGHTS["documentation"],
        score=float(score) if score is not None else None,
        inputs={
            "has_readme": inp.has_readme,
            "has_docs": inp.has_docs,
            "has_openspec": inp.has_openspec,
        },
    )


def _delivery(inp: HealthInputs) -> ComponentScore:
    parts: list[float] = []
    if inp.merge_rate is not None:
        parts.append(_clamp(inp.merge_rate * 100))
    merge_speed = _decay(inp.median_merge_seconds, best_days=1, worst_days=21)
    if merge_speed is not None:
        parts.append(merge_speed)
    resolve_speed = _decay(inp.median_issue_resolution_seconds, best_days=2, worst_days=30)
    if resolve_speed is not None:
        parts.append(resolve_speed)
    return ComponentScore(
        name="delivery",
        weight=_WEIGHTS["delivery"],
        score=_mean(parts),
        inputs={
            "merge_rate": inp.merge_rate,
            "median_merge_seconds": inp.median_merge_seconds,
            "median_issue_resolution_seconds": inp.median_issue_resolution_seconds,
        },
    )


def _maintenance(inp: HealthInputs) -> ComponentScore:
    open_total = inp.open_issues + inp.open_prs
    stale_total = inp.stale_issue_count + inp.stale_pr_count
    score = None if open_total == 0 else _clamp(100.0 * (1 - stale_total / open_total))
    return ComponentScore(
        name="maintenance",
        weight=_WEIGHTS["maintenance"],
        score=score,
        inputs={"open": open_total, "stale": stale_total},
    )


def _testing_ci(inp: HealthInputs) -> ComponentScore:
    known: list[float] = []
    if inp.signals.has_tests is not None:
        known.append(100.0 if inp.signals.has_tests else 0.0)
    if inp.signals.has_ci is not None:
        known.append(100.0 if inp.signals.has_ci else 0.0)
    return ComponentScore(
        name="testing_ci",
        weight=_WEIGHTS["testing_ci"],
        score=_mean(known),
        inputs={"has_tests": inp.signals.has_tests, "has_ci": inp.signals.has_ci},
    )


def _activity(inp: HealthInputs, now: datetime) -> ComponentScore:
    age = None if inp.last_activity is None else (now - inp.last_activity).total_seconds()
    return ComponentScore(
        name="activity",
        weight=_WEIGHTS["activity"],
        score=_decay(age, best_days=7, worst_days=180),
        inputs={"last_activity": inp.last_activity.isoformat() if inp.last_activity else None},
    )


def _findings(inp: HealthInputs, components: list[ComponentScore]) -> list[HealthFinding]:
    out: list[HealthFinding] = []
    if inp.synced and not inp.has_readme:
        out.append(HealthFinding(Severity.WARNING, "No README captured", "has_readme"))
    if inp.synced and not inp.has_docs:
        out.append(HealthFinding(Severity.INFO, "No documentation captured", "has_docs"))
    if inp.signals.has_ci is False:
        out.append(HealthFinding(Severity.WARNING, "No CI configured", "has_ci"))
    if inp.signals.has_tests is False:
        out.append(HealthFinding(Severity.WARNING, "No tests detected", "has_tests"))
    stale = inp.stale_issue_count + inp.stale_pr_count
    if stale:
        out.append(
            HealthFinding(
                Severity.WARNING if stale >= 5 else Severity.INFO,
                f"{stale} stale open item(s) past the stale threshold",
                "stale",
            )
        )
    activity = next(c for c in components if c.name == "activity")
    if activity.score is not None and activity.score < 40:
        out.append(HealthFinding(Severity.WARNING, "No recent activity", "activity"))
    order = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}
    return sorted(out, key=lambda f: order[f.severity])


class RepositoryHealthService:
    """Score a repository from its persisted metrics + file-tree signals."""

    def score(self, inp: HealthInputs, now: datetime) -> RepositoryHealth:
        if not inp.synced:
            return RepositoryHealth(components=[], overall=None, grade=None, has_data=False)

        components = [
            _documentation(inp),
            _delivery(inp),
            _maintenance(inp),
            _testing_ci(inp),
            _activity(inp, now),
        ]
        present = [(c.score, c.weight) for c in components if c.score is not None]
        total_weight = sum(w for _, w in present)
        overall = (
            sum(s * w for s, w in present) / total_weight if total_weight > 0 else None
        )
        return RepositoryHealth(
            components=components,
            overall=round(overall, 1) if overall is not None else None,
            grade=grade_for(overall),
            findings=_findings(inp, components),
        )
