from pathlib import Path

import duckdb
import pyarrow as pa
import pytest

from cloudcost.config.loader import PolicyConfig
from cloudcost.policies.models import Finding
from cloudcost.policies.runner import PolicyRunner

POLICIES_DIR = Path(__file__).resolve().parents[2] / "policies"


@pytest.fixture
def run_policy(tmp_path: Path):
    """Run one policy from the policies folder against small in-memory tables and return its findings."""

    def run(policy_name: str, tables: dict[str, pa.Table]) -> list[Finding]:
        db_path = tmp_path / "costs.duckdb"
        conn = duckdb.connect(str(db_path))
        try:
            for table_name, table in tables.items():
                conn.register("staged", table)
                conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM staged")
                conn.unregister("staged")
        finally:
            conn.close()

        policy = PolicyConfig(
            name=policy_name,
            type="sql",
            query_file=str(POLICIES_DIR / f"{policy_name}.sql"),
            severity="medium",
        )
        return PolicyRunner(str(db_path)).run_policy(policy)

    return run
