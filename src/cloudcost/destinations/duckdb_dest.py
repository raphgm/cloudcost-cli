import duckdb
import pyarrow as pa
from typing import Any

from cloudcost.core.registry import registry

@registry.register_destination("duckdb")
class DuckDBDestination:
    def __init__(self, config: dict):
        self.path = config.get("path")
        if not self.path:
            raise ValueError("duckdb destination requires 'path' in config")

    def load(self, table: pa.Table, target: Any, context: Any = None) -> None:
        table_name = target.table if hasattr(target, "table") and target.table else "default_table"
        
        # Connect to DuckDB
        conn = duckdb.connect(self.path)
        
        # We can register the pyarrow table as a view in DuckDB, then insert it.
        # This makes the Arrow memory directly queryable by DuckDB without a copy,
        # and then we persist it into the actual DuckDB table.
        conn.register("arrow_table_view", table)
        
        # Check if table exists
        exists = conn.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = ?", 
            [table_name]
        ).fetchone()[0] > 0
        
        # Handle merge modes
        mode = target.mode if hasattr(target, "mode") and target.mode else "overwrite"
        
        if not exists or mode == "overwrite":
            conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM arrow_table_view")
        elif mode == "append":
            conn.execute(f"INSERT INTO {table_name} SELECT * FROM arrow_table_view")
        elif mode == "merge":
            # MVP merge: For a real FinOps platform, this requires complex keys.
            # Here we do a simple replace if keys are provided, else append.
            keys = target.keys if hasattr(target, "keys") and target.keys else []
            if keys:
                # Delete existing matched rows and insert new
                keys_cond = " AND ".join([f"{table_name}.{k} = arrow_table_view.{k}" for k in keys])
                conn.execute(f"DELETE FROM {table_name} WHERE EXISTS (SELECT 1 FROM arrow_table_view WHERE {keys_cond})")
                conn.execute(f"INSERT INTO {table_name} SELECT * FROM arrow_table_view")
            else:
                conn.execute(f"INSERT INTO {table_name} SELECT * FROM arrow_table_view")
        
        conn.unregister("arrow_table_view")
        conn.close()
