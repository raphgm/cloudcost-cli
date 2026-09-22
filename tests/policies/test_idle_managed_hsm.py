import pyarrow as pa


def hsm_rows(*rows: tuple[str, str, float, float]) -> pa.Table:
    """Each row is (resource_id, sku, operation_count, hourly_price)."""
    return pa.table(
        {
            "resource_id": pa.array([r[0] for r in rows], type=pa.string()),
            "resource_name": pa.array([f"hsm-{r[0]}" for r in rows], type=pa.string()),
            "sku": pa.array([r[1] for r in rows], type=pa.string()),
            "operation_count": pa.array([r[2] for r in rows], type=pa.float64()),
            "hourly_price": pa.array([r[3] for r in rows], type=pa.float64()),
            "lookback_days": pa.array([7 for _ in rows], type=pa.int64()),
        }
    )


def test_managed_hsm_zero_operations_is_reported(run_policy) -> None:
    # Real Standard B1 price fetched from Microsoft's own published Key
    # Vault pricing page: $3.20/hour.
    findings = run_policy(
        "idle_managed_hsm",
        {"fact_idle_managed_hsm": hsm_rows(("hsm1", "Standard_B1", 0.0, 3.20))},
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.provider == "azure"
    assert finding.service_name == "Managed HSM"
    assert finding.estimated_impact == round(3.20 * 730, 2)
    assert finding.evidence["evidence_reason"] == "Managed HSM with 0 operations over 7 days (Standard_B1)"


def test_managed_hsm_with_activity_is_not_reported(run_policy) -> None:
    findings = run_policy(
        "idle_managed_hsm",
        {"fact_idle_managed_hsm": hsm_rows(("hsm1", "Standard_B1", 10.0, 3.20))},
    )

    assert findings == []


def test_managed_hsm_with_no_price_is_not_reported(run_policy) -> None:
    # An unrecognized SKU gets hourly_price=0.0 from the source; the
    # policy must not report a $0 finding as if it were real.
    findings = run_policy(
        "idle_managed_hsm",
        {"fact_idle_managed_hsm": hsm_rows(("hsm1", "UnknownSku", 0.0, 0.0))},
    )

    assert findings == []
