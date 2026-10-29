import pyarrow as pa


def fact_cost(rows: list[dict]) -> pa.Table:
    """Each row is provider, resource_id, service_name, billed_cost, usage_date."""
    return pa.table(
        {
            "provider": pa.array([r["provider"] for r in rows], type=pa.string()),
            "resource_id": pa.array([r["resource_id"] for r in rows], type=pa.string()),
            "service_name": pa.array([r["service_name"] for r in rows], type=pa.string()),
            "billed_cost": pa.array([r["billed_cost"] for r in rows], type=pa.float64()),
            "usage_date": pa.array([r["usage_date"] for r in rows], type=pa.string()),
        }
    )


def baseline_days(resource_id: str, n_days: int = 7, daily_cost: float = 10.0) -> list[dict]:
    """n_days of steady $daily_cost spend for one resource, starting 2026-01-01."""
    return [
        {
            "provider": "azure",
            "resource_id": resource_id,
            "service_name": "Virtual Machines",
            "billed_cost": daily_cost,
            "usage_date": f"2026-01-{day:02d}",
        }
        for day in range(1, n_days + 1)
    ]


def test_spend_spike_above_3x_trailing_average_is_flagged(run_policy) -> None:
    rows = baseline_days("vm-a", n_days=7, daily_cost=10.0)
    rows.append(
        {
            "provider": "azure",
            "resource_id": "vm-a",
            "service_name": "Virtual Machines",
            "billed_cost": 100.0,
            "usage_date": "2026-01-08",
        }
    )

    findings = run_policy("cost_anomaly", {"fact_cost": fact_cost(rows)})

    assert len(findings) == 1
    finding = findings[0]
    assert finding.provider == "azure"
    assert finding.resource_id == "vm-a"
    assert finding.service_name == "Virtual Machines"
    assert finding.estimated_impact == 100.0
    assert finding.evidence["spike_multiplier"] == 10.0
    assert finding.evidence["trailing_avg_7d"] == 10.0


def test_spike_below_3x_is_not_flagged(run_policy) -> None:
    rows = baseline_days("vm-a", n_days=7, daily_cost=10.0)
    rows.append(
        {
            "provider": "azure",
            "resource_id": "vm-a",
            "service_name": "Virtual Machines",
            "billed_cost": 25.0,
            "usage_date": "2026-01-08",
        }
    )

    assert run_policy("cost_anomaly", {"fact_cost": fact_cost(rows)}) == []


def test_steady_spend_is_not_flagged(run_policy) -> None:
    assert run_policy("cost_anomaly", {"fact_cost": fact_cost(baseline_days("vm-a", n_days=10))}) == []


def test_requires_a_full_7_day_baseline(run_policy) -> None:
    # Only 2 days of history: a day-2 spike must not be flagged against a
    # single-day "average" -- a real 7-day rolling average needs 7 prior days.
    rows = baseline_days("vm-a", n_days=1, daily_cost=10.0)
    rows.append(
        {
            "provider": "azure",
            "resource_id": "vm-a",
            "service_name": "Virtual Machines",
            "billed_cost": 100.0,
            "usage_date": "2026-01-02",
        }
    )

    assert run_policy("cost_anomaly", {"fact_cost": fact_cost(rows)}) == []


def test_anomaly_is_isolated_per_resource(run_policy) -> None:
    rows = baseline_days("vm-a", n_days=8, daily_cost=10.0)
    rows += baseline_days("vm-b", n_days=8, daily_cost=10.0)
    rows.append(
        {
            "provider": "azure",
            "resource_id": "vm-a",
            "service_name": "Virtual Machines",
            "billed_cost": 100.0,
            "usage_date": "2026-01-09",
        }
    )

    findings = run_policy("cost_anomaly", {"fact_cost": fact_cost(rows)})

    assert [f.resource_id for f in findings] == ["vm-a"]


def test_empty_table_returns_no_findings(run_policy) -> None:
    assert run_policy("cost_anomaly", {"fact_cost": fact_cost([])}) == []
