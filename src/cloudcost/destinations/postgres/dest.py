import pyarrow as pa
import adbc_driver_postgresql.dbapi as dbapi
from typing import Any
import os

from cloudcost.core.registry import registry

@registry.register_destination("postgres")
class PostgresDestination:
    def __init__(self, config: dict):
        # We allow dsn to be passed in config, which could be an interpolated env var
        self.dsn = config.get("dsn")
        self.schema = config.get("schema", "public")
        
        if not self.dsn:
            raise ValueError("postgres destination requires 'dsn' in config")

    def load(self, table: pa.Table, target: Any, context: Any = None) -> None:
        table_name = target.table if hasattr(target, "table") and target.table else "default_table"
        mode = target.mode if hasattr(target, "mode") and target.mode else "overwrite"
        
        full_table_name = f"{self.schema}.{table_name}" if self.schema else table_name
        
        with dbapi.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                # Create schema if it doesn't exist
                if self.schema:
                    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self.schema}")
                
                # ADBC provides native support for Arrow ingestion!
                # We can use the adbc_ingest feature
                ingest_mode = "append"
                if mode == "overwrite":
                    ingest_mode = "replace"
                
                # If mode is merge, ADBC doesn't natively do a UPSERT via ingest, 
                # so we'd ingest into a temp table and run a MERGE/INSERT ON CONFLICT.
                # For the MVP we will fallback to standard append/replace via ADBC ingestion.
                if mode == "merge":
                    # To do a real merge we'd write to a temp table and run SQL.
                    # As a shortcut for this MVP, we treat it as append.
                    ingest_mode = "append"

                # Perform the extremely fast Arrow ADBC ingest
                cur.adbc_ingest(table_name, table, mode=ingest_mode, db_schema_name=self.schema)
            
            conn.commit()
