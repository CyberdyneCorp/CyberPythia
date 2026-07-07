from app.domain.services.delivery_stats import (
    aging_buckets,
    backlog_forecast,
    bus_factor,
    classify_label_set,
    percentile,
    percentiles,
    work_mix,
)

_DAY = 86400.0


def test_percentile_interpolates_and_handles_empty() -> None:
    assert percentile([], 50) is None
    assert percentile([5.0], 95) == 5.0
    # 1..10 -> p50 midpoint 5.5
    assert percentile([float(i) for i in range(1, 11)], 50) == 5.5
    p = percentiles([float(i) for i in range(1, 101)])
    assert p.n == 100
    assert p.p50 is not None and 49 < p.p50 < 52
    assert p.p95 is not None and p.p95 > p.p85 > p.p50  # type: ignore[operator]


def test_percentiles_empty_all_none() -> None:
    p = percentiles([])
    assert (p.n, p.p50, p.p85, p.p95) == (0, None, None, None)


def test_aging_buckets() -> None:
    ages = [1 * _DAY, 10 * _DAY, 45 * _DAY, 200 * _DAY, 6.9 * _DAY]
    b = aging_buckets(ages)
    assert b == {"0-7": 2, "7-30": 1, "30-90": 1, "90+": 1}


def test_classify_and_work_mix() -> None:
    assert classify_label_set(["Bug", "p1"]) == "bug"
    assert classify_label_set(["enhancement"]) == "feature"
    assert classify_label_set(["refactor"]) == "tech_debt"
    assert classify_label_set(["documentation"]) == "docs"
    assert classify_label_set(["random"]) == "other"
    assert classify_label_set([]) == "other"
    mix = work_mix([["bug"], ["feature"], ["feature"], ["chore"], []])
    assert mix == {"feature": 2, "bug": 1, "tech_debt": 1, "docs": 0, "other": 1}


def test_bus_factor() -> None:
    assert bus_factor({}) is None
    assert bus_factor({"a": 8, "b": 1, "c": 1}) == 1  # a alone ≥ 50%
    assert bus_factor({"a": 3, "b": 3, "c": 3, "d": 3}) == 2  # top 2 = 6/12 = 50%


def test_backlog_forecast_paths() -> None:
    assert backlog_forecast(10, [5]).reason == "insufficient history"
    growing = backlog_forecast(10, [0, 0])
    assert growing.projected_days is None and growing.reason == "backlog not shrinking"
    clearing = backlog_forecast(20, [4, 6])  # avg 5/period
    assert clearing.projected_days == 4.0 and clearing.reason is None
    empty = backlog_forecast(0, [3, 3])
    assert empty.projected_days == 0.0
