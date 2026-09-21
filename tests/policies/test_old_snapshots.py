import pyarrow as pa


def snapshots(*rows: tuple[str, int, int]) -> pa.Table:
    """Each row is (resource_id, size_gb, age_days)."""
    return pa.table(
        {
            "resource_id": pa.array([r[0] for r in rows], type=pa.string()),
            "resource_name": pa.array([f"name-{r[0]}" for r in rows], type=pa.string()),
            "resource_group": pa.array(["rg" for _ in rows], type=pa.string()),
            "size_gb": pa.array([r[1] for r in rows], type=pa.int64()),
            "sku": pa.array(["Standard_LRS" for _ in rows], type=pa.string()),
            "age_days": pa.array([r[2] for r in rows], type=pa.int64()),
            "location": pa.array(["eastus" for _ in rows], type=pa.string()),
        }
    )


def test_flags_a_snapshot_older_than_30_days(run_policy) -> None:
    findings = run_policy("old_snapshots", {"fact_old_snapshots": snapshots(("snap1", 100, 45))})

    assert len(findings) == 1
    finding = findings[0]
    assert finding.provider == "azure"
    assert finding.service_name == "Snapshot"
    assert finding.resource_id == "snap1"
    assert finding.evidence["evidence_reason"] == "snapshot is 45 days old (100GB Standard_LRS)"


def test_a_snapshot_exactly_30_days_old_is_not_flagged(run_policy) -> None:
    findings = run_policy("old_snapshots", {"fact_old_snapshots": snapshots(("snap1", 100, 30))})

    assert findings == []


def test_a_snapshot_31_days_old_is_flagged(run_policy) -> None:
    findings = run_policy("old_snapshots", {"fact_old_snapshots": snapshots(("snap1", 100, 31))})

    assert [f.resource_id for f in findings] == ["snap1"]


def test_monthly_cost_is_size_times_five_cents(run_policy) -> None:
    findings = run_policy("old_snapshots", {"fact_old_snapshots": snapshots(("snap1", 100, 45))})

    assert findings[0].estimated_impact == 5.0


def test_monthly_cost_scales_with_snapshot_size(run_policy) -> None:
    findings = run_policy("old_snapshots", {"fact_old_snapshots": snapshots(("snap1", 33, 45))})

    assert findings[0].estimated_impact == 1.65


def test_only_old_snapshots_are_returned_from_a_mixed_table(run_policy) -> None:
    table = snapshots(("old", 10, 90), ("recent", 10, 3), ("older", 10, 400))

    findings = run_policy("old_snapshots", {"fact_old_snapshots": table})

    assert sorted(f.resource_id for f in findings) == ["old", "older"]


def test_empty_table_returns_no_findings(run_policy) -> None:
    assert run_policy("old_snapshots", {"fact_old_snapshots": snapshots()}) == []
