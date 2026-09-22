import pyarrow as pa


def kusto_rows(*rows: tuple[str, str, int, float, float, float]) -> pa.Table:
    return pa.table(
        {
            "resource_id": pa.array([r[0] for r in rows], type=pa.string()),
            "resource_name": pa.array([f"kusto-{r[0]}" for r in rows], type=pa.string()),
            "sku": pa.array([r[1] for r in rows], type=pa.string()),
            "instance_count": pa.array([r[2] for r in rows], type=pa.int64()),
            "total_ingestion_mb": pa.array([r[3] for r in rows], type=pa.float64()),
            "total_queries": pa.array([r[4] for r in rows], type=pa.float64()),
            "hourly_price_per_instance": pa.array([r[5] for r in rows], type=pa.float64()),
            "lookback_days": pa.array([7 for _ in rows], type=pa.int64()),
        }
    )


def test_kusto_cluster_with_zero_ingestion_and_queries_is_reported(run_policy) -> None:
    findings = run_policy(
        "idle_kusto_cluster",
        {
            "fact_idle_kusto_cluster": kusto_rows(
                ("cluster1", "Standard_E2a_v4", 2, 0.0, 0.0, 0.12)
            )
        },
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.provider == "azure"
    assert finding.service_name == "Azure Data Explorer Cluster"
    assert finding.estimated_impact == 175.2
    assert finding.evidence["evidence_reason"] == "cluster with 0 ingestion and 0 queries over 7 days (Standard_E2a_v4)"


def test_kusto_cluster_with_activity_is_not_reported(run_policy) -> None:
    findings = run_policy(
        "idle_kusto_cluster",
        {
            "fact_idle_kusto_cluster": kusto_rows(
                ("cluster1", "Standard_E2a_v4", 2, 150.0, 12.0, 0.12)
            )
        },
    )

    assert findings == []
