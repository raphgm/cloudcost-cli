import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real Azure Bastion session-count metric, confirmed via
# `az monitor metrics list-definitions --resource <bastion-id>` (real name:
# "sessions", exposed at Total aggregation only -- Average returns nulls).
# Real quirk: "sessions" only supports 5m/15m time grains, not the PT1H
# used by every other metric source in this project -- PT1H returns a
# BadRequest ("Commonly allowed time grains: 00:05:00,00:15:00").
@registry.register_source("azure.idle_bastion")
class AzureIdleBastionSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.idle_bastion requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        hosts_raw = subprocess.run(
            ["az", "network", "bastion", "list", "--resource-group", self.resource_group,
             "--query", "[].{id:id,name:name,sku:sku.name}", "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        hosts = json.loads(hosts_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for host in hosts:
            raw = subprocess.run(
                [
                    "az", "monitor", "metrics", "list",
                    "--resource", host["id"],
                    "--metric", "sessions",
                    "--aggregation", "Total",
                    "--interval", "PT15M",
                    "--start-time", start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "--end-time", end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ],
                capture_output=True, text=True, check=True,
            ).stdout
            parsed = json.loads(raw)

            total_sessions = 0.0
            for timeseries in parsed.get("value", []):
                for series in timeseries.get("timeseries", []):
                    for point in series.get("data", []):
                        total_sessions += point.get("total") or 0.0

            rows.append({
                "resource_id": host["id"].lower(),
                "resource_name": host["name"],
                "sku": host.get("sku", "Basic"),
                "total_sessions": total_sessions,
                "lookback_days": self.lookback_days,
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "sku": pa.array([], type=pa.string()),
                "total_sessions": pa.array([], type=pa.float64()),
                "lookback_days": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "sku": [r["sku"] for r in rows],
            "total_sessions": [r["total_sessions"] for r in rows],
            "lookback_days": [r["lookback_days"] for r in rows],
        })
