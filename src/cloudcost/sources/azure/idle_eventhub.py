import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real Event Hubs check: Standard-tier namespaces reserve a fixed number
# of Throughput Units, billed hourly whether messages actually flow or
# not. "IncomingMessages" confirmed via
# `az monitor metrics list-definitions --resource <namespace-id>`.
@registry.register_source("azure.idle_eventhub")
class AzureIdleEventHubSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.idle_eventhub requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        ns_raw = subprocess.run(
            ["az", "eventhubs", "namespace", "list", "--resource-group", self.resource_group,
             "--query", "[].{id:id,name:name,sku:sku.name,capacity:sku.capacity}", "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        namespaces = json.loads(ns_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for ns in namespaces:
            if ns.get("sku") != "Standard":
                continue

            raw = subprocess.run(
                [
                    "az", "monitor", "metrics", "list",
                    "--resource", ns["id"],
                    "--metric", "IncomingMessages",
                    "--aggregation", "Total",
                    "--interval", "PT1H",
                    "--start-time", start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "--end-time", end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ],
                capture_output=True, text=True, check=True,
            ).stdout
            parsed = json.loads(raw)

            total_messages = 0.0
            for timeseries in parsed.get("value", []):
                for series in timeseries.get("timeseries", []):
                    for point in series.get("data", []):
                        total_messages += point.get("total") or 0.0

            rows.append({
                "resource_id": ns["id"].lower(),
                "resource_name": ns["name"],
                "throughput_units": ns.get("capacity", 1),
                "total_incoming_messages": total_messages,
                "lookback_days": self.lookback_days,
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "throughput_units": pa.array([], type=pa.int64()),
                "total_incoming_messages": pa.array([], type=pa.float64()),
                "lookback_days": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "throughput_units": [r["throughput_units"] for r in rows],
            "total_incoming_messages": [r["total_incoming_messages"] for r in rows],
            "lookback_days": [r["lookback_days"] for r in rows],
        })
