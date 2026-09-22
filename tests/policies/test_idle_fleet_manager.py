import pyarrow as pa


def fleet_rows(*rows: tuple[str, int, str, float]) -> pa.Table:
    """Each row is (resource_id, member_cluster_count, hub_vm_size, hourly_price)."""
    return pa.table(
        {
            "resource_id": pa.array([r[0] for r in rows], type=pa.string()),
            "resource_name": pa.array([f"fleet-{r[0]}" for r in rows], type=pa.string()),
            "member_cluster_count": pa.array([r[1] for r in rows], type=pa.int64()),
            "hub_vm_size": pa.array([r[2] for r in rows], type=pa.string()),
            "hourly_price": pa.array([r[3] for r in rows], type=pa.float64()),
        }
    )


def test_fleet_with_zero_members_is_reported(run_policy) -> None:
    # Real Standard_DS3_v2 price confirmed live via the Retail Prices
    # API: $0.293/hour (eastus).
    findings = run_policy(
        "idle_fleet_manager",
        {"fact_idle_fleet_manager": fleet_rows(("fleet1", 0, "Standard_DS3_v2", 0.293))},
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.provider == "azure"
    assert finding.service_name == "AKS Fleet Manager (hub infrastructure)"
    assert finding.estimated_impact == round(0.293 * 730, 2)
    assert finding.evidence["evidence_reason"] == "Fleet hub with 0 member clusters attached (Standard_DS3_v2 node)"


def test_fleet_with_members_is_not_reported(run_policy) -> None:
    findings = run_policy(
        "idle_fleet_manager",
        {"fact_idle_fleet_manager": fleet_rows(("fleet1", 3, "Standard_DS3_v2", 0.293))},
    )

    assert findings == []


def test_fleet_with_no_live_price_is_not_reported(run_policy) -> None:
    # If the live price lookup failed (e.g. transient API issue), the
    # source returns hourly_price=0.0 and the policy must not report a
    # $0 finding as if it were real.
    findings = run_policy(
        "idle_fleet_manager",
        {"fact_idle_fleet_manager": fleet_rows(("fleet1", 0, "Standard_DS3_v2", 0.0))},
    )

    assert findings == []
