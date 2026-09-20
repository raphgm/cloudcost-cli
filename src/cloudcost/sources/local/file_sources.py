import pyarrow as pa
import pyarrow.csv as pv
import pyarrow.parquet as pq
from typing import Any

from cloudcost.core.registry import registry

@registry.register_source("local.csv")
class LocalCsvSource:
    def __init__(self, config: dict):
        self.path = config.get("path")
        if not self.path:
            raise ValueError("local.csv requires 'path' in config")

    def extract(self, context: Any = None) -> pa.Table:
        # In a real implementation, we would handle chunking for large files.
        # For MVP, we load the entire file into a pyarrow.Table.
        return pv.read_csv(self.path)

@registry.register_source("local.parquet")
class LocalParquetSource:
    def __init__(self, config: dict):
        self.path = config.get("path")
        if not self.path:
            raise ValueError("local.parquet requires 'path' in config")

    def extract(self, context: Any = None) -> pa.Table:
        return pq.read_table(self.path)
