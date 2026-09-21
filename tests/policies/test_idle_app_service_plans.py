import pyarrow as pa


def plans(*rows: tuple[str, str]) -> pa.Table:
    """Each row is (resource_id, sku)."""
    return pa.table(
        {
            "resource_id": pa.array([r[0] for r in rows], type=pa.string()),
            "resource_name": pa.array([f"name-{r[0]}" for r in rows], type=pa.string()),
            "resource_group": pa.array(["rg" for _ in rows], type=pa.string()),
            "sku": pa.array([r[1] for r in rows], type=pa.string()),
        }
    )


def test_free_tier_plan_is_reported_at_zero_dollars(run_policy) -> None:
    findings = run_policy("idle_app_service_plans", {"fact_idle_app_service_plans": plans(("plan1", "F1"))})

    assert len(findings) == 1
    finding = findings[0]
    assert finding.provider == "azure"
    assert finding.service_name == "App Service Plan"
    assert finding.estimated_impact == 0.0
    assert finding.evidence["evidence_reason"] == "App Service Plan with 0 deployed apps (F1 tier)"


def test_paid_tier_plan_uses_the_documented_basic_price_estimate(run_policy) -> None:
    findings = run_policy("idle_app_service_plans", {"fact_idle_app_service_plans": plans(("plan1", "B1"))})

    assert findings[0].estimated_impact == 13.14
    assert findings[0].evidence["evidence_reason"] == "App Service Plan with 0 deployed apps (B1 tier)"


def test_every_plan_row_becomes_a_finding(run_policy) -> None:
    table = plans(("a", "F1"), ("b", "B1"), ("c", "S1"))

    findings = run_policy("idle_app_service_plans", {"fact_idle_app_service_plans": table})

    assert sorted(f.resource_id for f in findings) == ["a", "b", "c"]


def test_empty_table_returns_no_findings(run_policy) -> None:
    assert run_policy("idle_app_service_plans", {"fact_idle_app_service_plans": plans()}) == []
