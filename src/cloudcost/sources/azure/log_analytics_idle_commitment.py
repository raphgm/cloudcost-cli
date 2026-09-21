import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: Log Analytics workspaces on a CapacityReservation
# (Commitment Tier) SKU pay a fixed daily rate for reserved GB/day
# regardless of how much is actually ingested -- a real, easy-to-forget
# waste pattern (teams pick a tier for a launch, ingestion drops after,
# nobody revisits it).
# "Ingestion Volume" confirmed via
# `az monitor metrics list-definitions --resource <workspace-id>` --
# the real metric name has a literal space in it, unlike every other
# metric name in this project (e.g. "PEBytesIn", "sessions").
@registry.register_source("azure.log_analytics_idle_commitment")
class AzureLogAnalyticsIdleCommitmentSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.log_analytics_idle_commitment requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        ws_raw = subprocess.run(
            ["az", "monitor", "log-analytics", "workspace", "list",
             "--resource-group", self.resource_group,
             "--query", "[].{id:id,name:name,sku:sku.name,level:sku.capacityReservationLevel}", "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        workspaces = json.loads(ws_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for ws in workspaces:
            if ws.get("sku") != "CapacityReservation":
                continue

            raw = subprocess.run(
                [
                    "az", "monitor", "metrics", "list",
                    "--resource", ws["id"],
                    "--metric", "Ingestion Volume",
                    "--aggregation", "Total",
                    "--interval", "PT1H",
                    "--start-time", start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "--end-time", end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ],
                capture_output=True, text=True, check=True,
            ).stdout
            parsed = json.loads(raw)

            total_bytes = 0.0
            for timeseries in parsed.get("value", []):
                for series in timeseries.get("timeseries", []):
                    for point in series.get("data", []):
                        total_bytes += point.get("total") or 0.0

            rows.append({
                "resource_id": ws["id"].lower(),
                "resource_name": ws["name"],
                "reserved_gb_per_day": ws.get("level", 100),
                "total_gb_ingested": total_bytes / (1024 ** 3),
                "lookback_days": self.lookback_days,
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "reserved_gb_per_day": pa.array([], type=pa.int64()),
                "total_gb_ingested": pa.array([], type=pa.float64()),
                "lookback_days": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "reserved_gb_per_day": [r["reserved_gb_per_day"] for r in rows],
            "total_gb_ingested": [r["total_gb_ingested"] for r in rows],
            "lookback_days": [r["lookback_days"] for r in rows],
        })
