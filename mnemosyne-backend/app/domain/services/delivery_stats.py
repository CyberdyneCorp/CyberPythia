"""Pure PM/PO delivery statistics (spec: delivery-intelligence).

Percentiles, aging buckets, work-mix classification, bus factor, and trailing-rate
forecasting — all pure and absent-not-zero (empty population / short history →
``None``, never a fabricated 0).
"""

from collections import Counter
from dataclasses import dataclass

_DAY = 86400.0

# Aging buckets in days: [0-7), [7-30), [30-90), [90+)
AGING_BUCKETS = ("0-7", "7-30", "30-90", "90+")

# Default label -> work class map (lowercased substrings). Overridable by config.
DEFAULT_WORK_MIX_MAP: dict[str, str] = {
    "bug": "bug",
    "defect": "bug",
    "regression": "bug",
    "feature": "feature",
    "enhancement": "feature",
    "tech-debt": "tech_debt",
    "tech debt": "tech_debt",
    "refactor": "tech_debt",
    "chore": "tech_debt",
    "docs": "docs",
    "documentation": "docs",
}
WORK_CLASSES = ("feature", "bug", "tech_debt", "docs", "other")


@dataclass(frozen=True, slots=True)
class Percentiles:
    n: int
    p50: float | None
    p85: float | None
    p95: float | None


def percentile(values: list[float], q: float) -> float | None:
    """Linear-interpolation percentile; ``None`` for an empty population."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = q / 100.0 * (len(ordered) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    frac = rank - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * frac


def percentiles(values: list[float]) -> Percentiles:
    return Percentiles(
        n=len(values),
        p50=percentile(values, 50),
        p85=percentile(values, 85),
        p95=percentile(values, 95),
    )


def aging_buckets(ages_seconds: list[float]) -> dict[str, int]:
    """Bucket open-item ages into 0-7 / 7-30 / 30-90 / 90+ day buckets."""
    out: dict[str, int] = {b: 0 for b in AGING_BUCKETS}
    for age in ages_seconds:
        days = age / _DAY
        if days < 7:
            out["0-7"] += 1
        elif days < 30:
            out["7-30"] += 1
        elif days < 90:
            out["30-90"] += 1
        else:
            out["90+"] += 1
    return out


def classify_label_set(
    labels: list[str], mapping: dict[str, str] | None = None
) -> str:
    """Map an item's labels to a single work class (first match wins; else 'other')."""
    table = mapping or DEFAULT_WORK_MIX_MAP
    for label in labels:
        low = label.lower()
        for key, cls in table.items():
            if key in low:
                return cls
    return "other"


def work_mix(
    label_sets: list[list[str]], mapping: dict[str, str] | None = None
) -> dict[str, int]:
    counts: Counter[str] = Counter(classify_label_set(ls, mapping) for ls in label_sets)
    return {cls: counts.get(cls, 0) for cls in WORK_CLASSES}


def bus_factor(by_author: dict[str, int]) -> int | None:
    """Smallest number of top authors covering ≥ 50% of contributions; ``None`` if none."""
    total = sum(by_author.values())
    if total <= 0:
        return None
    cumulative = 0
    for i, count in enumerate(sorted(by_author.values(), reverse=True), start=1):
        cumulative += count
        if cumulative * 2 >= total:
            return i
    return len(by_author)


@dataclass(frozen=True, slots=True)
class Forecast:
    projected_days: float | None
    close_rate_per_day: float | None
    reason: str | None


def backlog_forecast(
    open_count: int, closed_deltas: list[int], min_points: int = 2
) -> Forecast:
    """Project days-to-clear from the trailing close rate.

    ``closed_deltas`` are per-period counts of items closed (from the snapshot
    series). ``None`` projection with a reason when history is too short, the rate
    is non-positive, or the backlog is already empty.
    """
    if len(closed_deltas) < min_points:
        return Forecast(None, None, "insufficient history")
    rate_per_period = sum(closed_deltas) / len(closed_deltas)
    if rate_per_period <= 0:
        return Forecast(None, 0.0, "backlog not shrinking")
    if open_count == 0:
        return Forecast(0.0, rate_per_period, None)
    return Forecast(open_count / rate_per_period, rate_per_period, None)
