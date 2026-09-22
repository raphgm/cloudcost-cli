import pyarrow as pa


def fleet_rows(*rows: tuple[str, str, int, float]) -> pa.Table:
    return pa.table(
        {
            "resource_id": pa.array([r[0] for r in rows], type=pa.string()),
            "resource_name": pa.array([f"fleet-{r[0]}" for r in rows], type=pa.string()),
            "sku": pa.array([r[1] for r in rows], type=pa.string()),
            "member_cluster_count": pa.array([r[2] for r in rows], type=pa.int64()),
            "update_runs": pa.array([r[3] for r in rows], type=pa.float64()),
            "lookback_days": pa.array([7 for _ in rows], type=pa.int64()),
        }
    )


def test_fleet_with_zero_member_clusters_is_reported(run_policy) -> None:
    findings = run_policy("idle_fleet_manager", {"fact_idle_fleet_manager": fleet_rows(("fleet1", "Standard", 0, 0.0))})

    assert len(findings) == 1
    finding = findings[0]
    assert finding.provider == "azure"
    assert finding.service_name == "Fleet Manager"
    assert finding.estimated_impact == 30.0
    assert finding.evidence["evidence_reason"] == "Fleet Manager with 0 member clusters over 7 days (Standard)"


def test_fleet_with_real_activity_is_not_reported(run_policy) -> None:
    findings = run_policy("idle_fleet_manager", {"fact_idle_fleet_manager": fleet_rows(("fleet1", "Standard", 1, 10.0))})

    assert findings == []
