import pyarrow as pa


def gremlin_accounts(*rows: tuple[str, str, int, float, int]) -> pa.Table:
    """Each row is (resource_id, resource_name, provisioned_ru, total_ru_consumed, lookback_days)."""
    return pa.table(
        {
            "resource_id": pa.array([r[0] for r in rows], type=pa.string()),
            "resource_name": pa.array([r[1] for r in rows], type=pa.string()),
            "provisioned_ru": pa.array([r[2] for r in rows], type=pa.int64()),
            "total_ru_consumed": pa.array([r[3] for r in rows], type=pa.float64()),
            "lookback_days": pa.array([r[4] for r in rows], type=pa.int64()),
        }
    )


def test_flags_idle_gremlin_account_below_consumption_threshold(run_policy) -> None:
    table = gremlin_accounts(
        (
            "/subscriptions/sub/resourcegroups/rg/providers/microsoft.documentdb/databaseaccounts/gremlindb1",
            "gremlindb1",
            1000,
            5.0,
            7,
        )
    )

    findings = run_policy(
        "cosmosdb_gremlin_idle_ru",
        {"fact_cosmosdb_gremlin_idle_ru": table},
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.provider == "azure"
    assert finding.service_name == "Azure Cosmos DB for Gremlin"
    assert finding.estimated_impact == 58.40  # (1000 / 100) * 0.008 * 730 = 58.4
    assert finding.evidence["provisioned_ru"] == 1000
    assert finding.evidence["total_ru_consumed"] == 5.0
    assert finding.evidence["lookback_days"] == 7
    assert (
        finding.evidence["evidence_reason"]
        == "1000 RU/s provisioned, only 5.0 RU consumed over 7 days"
    )


def test_active_gremlin_account_is_not_flagged(run_policy) -> None:
    # 100 RU consumed >= 1% of 1000 provisioned RU
    table = gremlin_accounts(
        (
            "/subscriptions/sub/resourcegroups/rg/providers/microsoft.documentdb/databaseaccounts/activegremlin",
            "activegremlin",
            1000,
            100.0,
            7,
        )
    )

    findings = run_policy(
        "cosmosdb_gremlin_idle_ru",
        {"fact_cosmosdb_gremlin_idle_ru": table},
    )

    assert findings == []


def test_account_with_zero_provisioned_ru_is_not_flagged(run_policy) -> None:
    table = gremlin_accounts(
        (
            "/subscriptions/sub/resourcegroups/rg/providers/microsoft.documentdb/databaseaccounts/zero-ru",
            "zero-ru",
            0,
            0.0,
            7,
        )
    )

    findings = run_policy(
        "cosmosdb_gremlin_idle_ru",
        {"fact_cosmosdb_gremlin_idle_ru": table},
    )

    assert findings == []


def test_mixed_accounts_returns_only_idle(run_policy) -> None:
    table = gremlin_accounts(
        (
            "/subscriptions/sub/resourcegroups/rg/providers/microsoft.documentdb/databaseaccounts/idle-account",
            "idle-account",
            400,
            1.0,
            7,
        ),
        (
            "/subscriptions/sub/resourcegroups/rg/providers/microsoft.documentdb/databaseaccounts/busy-account",
            "busy-account",
            400,
            5000.0,
            7,
        ),
    )

    findings = run_policy(
        "cosmosdb_gremlin_idle_ru",
        {"fact_cosmosdb_gremlin_idle_ru": table},
    )

    assert len(findings) == 1
    assert "idle-account" in findings[0].resource_id
    assert findings[0].estimated_impact == 23.36  # (400 / 100) * 0.008 * 730 = 23.36


def test_empty_table_returns_no_findings(run_policy) -> None:
    table = gremlin_accounts()

    assert (
        run_policy(
            "cosmosdb_gremlin_idle_ru",
            {"fact_cosmosdb_gremlin_idle_ru": table},
        )
        == []
    )
