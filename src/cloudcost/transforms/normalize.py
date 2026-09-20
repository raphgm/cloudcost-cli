import pyarrow as pa
from typing import Any

from cloudcost.core.registry import registry

@registry.register_transform("focus.normalize")
class FocusNormalizeTransform:
    def __init__(self, config: dict = None):
        self.config = config or {}

    def transform(self, table: pa.Table, context: Any = None) -> pa.Table:
        # In a real implementation, this would enforce the strict FOCUS schema.
        # For the MVP, we act as a passthrough to demonstrate the end-to-end flow.
        # We might add a 'normalized_at' column to prove it ran.
        import pyarrow.compute as pc
        import datetime
        
        # Add a dummy normalized_at timestamp to prove transform occurred
        normalized_at = pa.array([datetime.datetime.now(datetime.timezone.utc)] * table.num_rows)
        if "normalized_at" not in table.schema.names:
            table = table.append_column("normalized_at", normalized_at)
            
        return table
