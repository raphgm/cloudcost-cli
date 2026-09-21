import pyarrow as pa


def registries(*rows: tuple[str, str]) -> pa.Table:
    """Each row is (resource_id, sku)."""
    return pa.table(
        {
            "resource_id": pa.array([r[0] for r in rows], type=pa.string()),
            "resource_name": pa.array([f"name-{r[0]}" for r in rows], type=pa.string()),
            "resource_group": pa.array(["rg" for _ in rows], type=pa.string()),
            "sku": pa.array([r[1] for r in rows], type=pa.string()),
        }
    )


def test_standard_registry_is_priced_at_the_daily_rate_times_30(run_policy) -> None:
    findings = run_policy(
        "idle_container_registries", {"fact_idle_container_registries": registries(("reg1", "Standard"))}
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.provider == "azure"
    assert finding.service_name == "Container Registry"
    assert finding.estimated_impact == 20.0
    assert finding.evidence["evidence_reason"] == "idle Container Registry, 0 repositories (Standard tier)"


def test_premium_registry_is_priced_higher_than_standard(run_policy) -> None:
    findings = run_policy(
        "idle_container_registries", {"fact_idle_container_registries": registries(("reg1", "Premium"))}
    )

    assert findings[0].estimated_impact == 50.0
    assert findings[0].evidence["evidence_reason"] == "idle Container Registry, 0 repositories (Premium tier)"


def test_every_registry_row_becomes_a_finding(run_policy) -> None:
    table = registries(("a", "Standard"), ("b", "Premium"), ("c", "Standard"))

    findings = run_policy("idle_container_registries", {"fact_idle_container_registries": table})

    assert sorted(f.resource_id for f in findings) == ["a", "b", "c"]


def test_empty_table_returns_no_findings(run_policy) -> None:
    table = registries()

    assert run_policy("idle_container_registries", {"fact_idle_container_registries": table}) == []
