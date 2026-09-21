import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real Azure Firewall check: a firewall is a fixed hourly deployment cost
# (Basic/Standard/Premium tier) whether or not any traffic actually passes
# through it. "DataProcessed" (Total, bytes) confirmed via
# `az monitor metrics list-definitions --resource <firewall-id>`.
@registry.register_source("azure.idle_firewall")
class AzureIdleFirewallSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.idle_firewall requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        fws_raw = subprocess.run(
            ["az", "network", "firewall", "list", "--resource-group", self.resource_group,
             "--query", "[].{id:id,name:name,tier:sku.tier}", "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        fws = json.loads(fws_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for fw in fws:
            raw = subprocess.run(
                [
                    "az", "monitor", "metrics", "list",
                    "--resource", fw["id"],
                    "--metric", "DataProcessed",
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
                "resource_id": fw["id"].lower(),
                "resource_name": fw["name"],
                "tier": fw.get("tier", "Standard"),
                "total_bytes_processed": total_bytes,
                "lookback_days": self.lookback_days,
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "tier": pa.array([], type=pa.string()),
                "total_bytes_processed": pa.array([], type=pa.float64()),
                "lookback_days": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "tier": [r["tier"] for r in rows],
            "total_bytes_processed": [r["total_bytes_processed"] for r in rows],
            "lookback_days": [r["lookback_days"] for r in rows],
        })
