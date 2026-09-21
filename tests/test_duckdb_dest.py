from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa

from cloudcost.destinations.duckdb_dest import DuckDBDestination


@dataclass
class Target:
    table: str
    mode: str
    keys: list[str] | None = None


def make_table(ids: list[int], costs: list[float]) -> pa.Table:
    return pa.table({"id": ids, "cost": costs})


def read_rows(db_path: Path, table_name: str) -> list[tuple]:
    import duckdb

    conn = duckdb.connect(str(db_path))
    try:
        return conn.execute(
            f"SELECT id, cost FROM {table_name} ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


def test_overwrite_replaces_existing_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "costs.duckdb"
    destination = DuckDBDestination({"path": str(db_path)})

    destination.load(make_table([1, 2], [10.0, 20.0]), Target("costs", "overwrite"))
    destination.load(make_table([3], [30.0]), Target("costs", "overwrite"))

    assert read_rows(db_path, "costs") == [(3, 30.0)]


def test_append_preserves_existing_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "costs.duckdb"
    destination = DuckDBDestination({"path": str(db_path)})

    destination.load(make_table([1], [10.0]), Target("costs", "overwrite"))
    destination.load(make_table([2], [20.0]), Target("costs", "append"))

    assert read_rows(db_path, "costs") == [(1, 10.0), (2, 20.0)]


def test_merge_replaces_rows_matching_keys(tmp_path: Path) -> None:
    db_path = tmp_path / "costs.duckdb"
    destination = DuckDBDestination({"path": str(db_path)})

    destination.load(make_table([1, 2], [10.0, 20.0]), Target("costs", "overwrite"))
    destination.load(
        make_table([2, 3], [25.0, 30.0]),
        Target("costs", "merge", keys=["id"]),
    )

    assert read_rows(db_path, "costs") == [(1, 10.0), (2, 25.0), (3, 30.0)]
