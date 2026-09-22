import pyarrow as pa


def apim_rows(*rows: tuple[str, str, int, float, float]) -> pa.Table:
    """Each row is (resource_id, sku, unit_count, total_requests, hourly_price_per_unit)."""
    return pa.table(
        {
            "resource_id": pa.array([r[0] for r in rows], type=pa.string()),
            "resource_name": pa.array([f"apim-{r[0]}" for r in rows], type=pa.string()),
            "sku": pa.array([r[1] for r in rows], type=pa.string()),
            "unit_count": pa.array([r[2] for r in rows], type=pa.int64()),
            "total_requests": pa.array([r[3] for r in rows], type=pa.float64()),
            "hourly_price_per_unit": pa.array([r[4] for r in rows], type=pa.float64()),
            "lookback_days": pa.array([7 for _ in rows], type=pa.int64()),
        }
    )


def test_apim_zero_requests_is_reported(run_policy) -> None:
    # Real Developer-tier price confirmed live via the Retail Prices API:
    # $0.0658/hour (eastus).
    findings = run_policy("idle_apim", {"fact_idle_apim": apim_rows(("apim1", "Developer", 1, 0.0, 0.0658))})

    assert len(findings) == 1
    finding = findings[0]
    assert finding.provider == "azure"
    assert finding.service_name == "API Management"
    assert finding.estimated_impact == round(0.0658 * 730, 2)
    assert finding.evidence["evidence_reason"] == "API Management with 0 requests over 7 days (Developer)"


def test_apim_with_activity_is_not_reported(run_policy) -> None:
    findings = run_policy("idle_apim", {"fact_idle_apim": apim_rows(("apim1", "Developer", 1, 10.0, 0.0658))})

    assert findings == []


def test_apim_price_scales_with_tier_and_unit_count(run_policy) -> None:
    # Real Standard-tier price confirmed live: $0.9407/hour (eastus).
    findings = run_policy("idle_apim", {"fact_idle_apim": apim_rows(("apim2", "Standard", 2, 0.0, 0.9407))})

    assert findings[0].estimated_impact == round(2 * 0.9407 * 730, 2)


def test_apim_consumption_tier_has_no_price_and_is_not_reported(run_policy) -> None:
    # Consumption tier is pay-per-call; the source never assigns it a
    # positive hourly_price_per_unit, and the policy excludes zero-price
    # rows so a Consumption instance can't be reported as idle waste.
    findings = run_policy("idle_apim", {"fact_idle_apim": apim_rows(("apim3", "Consumption", 1, 0.0, 0.0))})

    assert findings == []
