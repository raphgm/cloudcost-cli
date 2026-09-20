import pyarrow as pa
from typing import Any

from cloudcost.core.registry import registry

@registry.register_transform("focus.normalize")
class FocusNormalizeTransform:
    def __init__(self, config: dict = None):
        self.config = config or {}

    def transform(self, table: pa.Table, context: Any = None) -> pa.Table:
        # This used to be a pure passthrough that only appended a
        # `normalized_at` column, despite the transform's name and the
        # bundled policies (policies/unallocated_costs.sql,
        # policies/zero_utilization.sql) expecting real FOCUS-schema
        # columns (provider, service_name, billed_cost, resource_id). Every
        # provider's raw export uses different column names (Azure:
        # ServiceName/PreTaxCost, AWS CUR: lineItem/ProductCode/
        # lineItem/UnblendedCost, etc.) that this transform never had
        # verified ground truth for across all four providers — so instead
        # of guessing at schemas, the pipeline config now declares the
        # mapping explicitly via this transform's own `config` block
        # (TransformConfig.config already existed in the schema; it was
        # just never read). See cloudcost.azure-real.yml for a real
        # example verified against a live Azure Cost Management export.
        import datetime

        provider = self.config.get("provider")
        column_map: dict = self.config.get("column_map", {})

        rename_from = [c for c in column_map if c in table.schema.names]
        for source_col in rename_from:
            target_col = column_map[source_col]
            idx = table.schema.get_field_index(source_col)
            table = table.rename_columns(
                [target_col if i == idx else name for i, name in enumerate(table.schema.names)]
            )

        if provider is not None:
            provider_col = pa.array([provider] * table.num_rows)
            if "provider" in table.schema.names:
                idx = table.schema.get_field_index("provider")
                table = table.set_column(idx, "provider", provider_col)
            else:
                table = table.append_column("provider", provider_col)

        # Add a normalized_at timestamp to prove the transform actually ran.
        normalized_at = pa.array([datetime.datetime.now(datetime.timezone.utc)] * table.num_rows)
        if "normalized_at" not in table.schema.names:
            table = table.append_column("normalized_at", normalized_at)

        return table
