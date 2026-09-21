from pathlib import Path

import duckdb
import pyarrow as pa

from cloudcost.config.loader import PolicyConfig
from cloudcost.policies.models import Finding
from cloudcost.policies.runner import PolicyRunner

POLICY_FILE = Path(__file__).resolve().parents[2] / "policies" / "aks_idle_nodepool.sql"


def make_nodepools(rows: list[dict]) -> pa.Table:
    return pa.table(
        {
            "resource_id": pa.array([r["resource_id"] for r in rows], type=pa.string()),
            "resource_name": pa.array([r["resource_name"] for r in rows], type=pa.string()),
            "vm_size": pa.array([r["vm_size"] for r in rows], type=pa.string()),
            "node_count": pa.array([r["node_count"] for r in rows], type=pa.int64()),
            "avg_cpu_percent": pa.array([r["avg_cpu_percent"] for r in rows], type=pa.float64()),
            "hourly_price_per_node": pa.array(
                [r["hourly_price_per_node"] for r in rows], type=pa.float64()
            ),
            "lookback_days": pa.array([r["lookback_days"] for r in rows], type=pa.int64()),
        }
    )


def nodepool(**overrides) -> dict:
    row = {
        "resource_id": "/subscriptions/s/resourcegroups/rg/providers/vmss/pool1",
        "resource_name": "cluster1/pool1",
        "vm_size": "Standard_D2s_v3",
        "node_count": 3,
        "avg_cpu_percent": 4.0,
        "hourly_price_per_node": 0.10,
        "lookback_days": 7,
    }
    row.update(overrides)
    return row


def run_policy(tmp_path: Path, rows: list[dict], policy_file: Path = POLICY_FILE) -> list[Finding]:
    db_path = tmp_path / "costs.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.register("nodepools", make_nodepools(rows))
        conn.execute("CREATE TABLE fact_aks_idle_nodepool AS SELECT * FROM nodepools")
    finally:
        conn.close()

    policy = PolicyConfig(
        name="aks-idle-nodepool",
        type="sql",
        query_file=str(policy_file),
        severity="medium",
    )
    return PolicyRunner(str(db_path)).run_policy(policy)


def test_flags_nodepool_below_cpu_threshold(tmp_path: Path) -> None:
    findings = run_policy(tmp_path, [nodepool()])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.provider == "azure"
    assert finding.service_name == "AKS Node Pool"
    assert finding.severity == "medium"
    assert finding.resource_id == "/subscriptions/s/resourcegroups/rg/providers/vmss/pool1"
    assert finding.evidence["evidence_reason"] == (
        "3 x Standard_D2s_v3 nodes averaging 4.0% CPU over 7 days"
    )


def test_monthly_cost_is_nodes_times_hourly_price_times_730(tmp_path: Path) -> None:
    findings = run_policy(tmp_path, [nodepool(node_count=3, hourly_price_per_node=0.10)])

    assert findings[0].estimated_impact == 219.0


def test_monthly_cost_is_rounded_to_two_decimals(tmp_path: Path) -> None:
    findings = run_policy(tmp_path, [nodepool(node_count=2, hourly_price_per_node=0.0777)])

    assert findings[0].estimated_impact == 113.44


def test_cpu_at_the_threshold_is_not_flagged(tmp_path: Path) -> None:
    findings = run_policy(tmp_path, [nodepool(avg_cpu_percent=10.0)])

    assert findings == []


def test_busy_nodepool_is_not_flagged(tmp_path: Path) -> None:
    findings = run_policy(tmp_path, [nodepool(avg_cpu_percent=45.0)])

    assert findings == []


def test_nodepool_without_a_price_is_not_flagged(tmp_path: Path) -> None:
    findings = run_policy(tmp_path, [nodepool(hourly_price_per_node=0.0)])

    assert findings == []


def test_only_idle_nodepools_are_returned_from_a_mixed_table(tmp_path: Path) -> None:
    rows = [
        nodepool(resource_id="idle", avg_cpu_percent=2.0),
        nodepool(resource_id="busy", avg_cpu_percent=60.0),
        nodepool(resource_id="unpriced", avg_cpu_percent=1.0, hourly_price_per_node=0.0),
    ]

    findings = run_policy(tmp_path, rows)

    assert [f.resource_id for f in findings] == ["idle"]


def test_empty_table_returns_no_findings(tmp_path: Path) -> None:
    assert run_policy(tmp_path, []) == []
