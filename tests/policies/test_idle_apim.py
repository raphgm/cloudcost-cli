import pyarrow as pa


def apim_rows(*rows: tuple[str, str, int, float]) -> pa.Table:
    return pa.table(
        {
            "resource_id": pa.array([r[0] for r in rows], type=pa.string()),
            "resource_name": pa.array([f"apim-{r[0]}" for r in rows], type=pa.string()),
            "sku": pa.array([r[1] for r in rows], type=pa.string()),
            "unit_count": pa.array([r[2] for r in rows], type=pa.int64()),
            "total_requests": pa.array([r[3] for r in rows], type=pa.float64()),
            "lookback_days": pa.array([7 for _ in rows], type=pa.int64()),
        }
    )


def test_apim_zero_requests_is_reported(run_policy) -> None:
    findings = run_policy("idle_apim", {"fact_idle_apim": apim_rows(("apim1", "Standard", 1, 0.0))})

    assert len(findings) == 1
    finding = findings[0]
    assert finding.provider == "azure"
    assert finding.service_name == "API Management"
    assert finding.estimated_impact == 30.0
    assert finding.evidence["evidence_reason"] == "API Management with 0 requests over 7 days (Standard)"


def test_apim_with_activity_is_not_reported(run_policy) -> None:
    findings = run_policy("idle_apim", {"fact_idle_apim": apim_rows(("apim1", "Standard", 1, 10.0))})

    assert findings == []
