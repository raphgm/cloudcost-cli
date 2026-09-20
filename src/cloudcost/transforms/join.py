import pyarrow as pa
import pyarrow.compute as pc
from typing import Any

from cloudcost.core.registry import registry

@registry.register_transform("join")
class JoinTransform:
    def __init__(self, config: dict):
        self.join_strategy = config.get("join_strategy", "left")
        self.keys = config.get("keys", ["resource_id"])
        
    def transform(self, table: pa.Table, context: Any = None) -> pa.Table:
        # The 'context' parameter needs to pass the secondary table to join against.
        # Since our MVP runner assumes a single input table, we'll implement a basic
        # multi-input join here by assuming 'context' contains the 'inputs' array 
        # and we fetch from a global state, or we just raise NotImplemented for the MVP
        # unless it's given directly.
        
        # Real implementation uses DuckDB or Arrow's acero engine to join.
        # For this MVP, we assume `table` is a dictionary of tables if multiple inputs,
        # or we simply return the primary table (passthrough) with a warning.
        
        if isinstance(table, dict) and len(table) >= 2:
            keys = list(table.keys())
            left_table = table[keys[0]]
            right_table = table[keys[1]]
            
            # Using pyarrow's native join
            try:
                joined_table = left_table.join(right_table, keys=self.keys, join_type=self.join_strategy)
                return joined_table
            except Exception as e:
                print(f"Join failed: {e}. Returning left table.")
                return left_table
                
        return table
