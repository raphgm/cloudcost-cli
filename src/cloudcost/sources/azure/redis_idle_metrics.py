import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real Azure Cache for Redis connected-client metric, confirmed against a
# live instance via `az monitor metrics list-definitions` (real name:
# "connectedclients", lowercase, no separators -- not documented
# consistently anywhere, had to check rather than guess).
@registry.register_source("azure.redis_idle_metrics")
class AzureRedisIdleMetricsSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.redis_idle_metrics requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        caches_raw = subprocess.run(
            ["az", "redis", "list", "--resource-group", self.resource_group, "--query", "[].{id:id,name:name}", "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        caches = json.loads(caches_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for cache in caches:
            raw = subprocess.run(
                [
                    "az", "monitor", "metrics", "list",
                    "--resource", cache["id"],
                    "--metric", "connectedclients",
                    "--aggregation", "Average",
                    "--interval", "PT1H",
                    "--start-time", start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "--end-time", end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ],
                capture_output=True, text=True, check=True,
            ).stdout
            parsed = json.loads(raw)

            for timeseries in parsed.get("value", []):
                for series in timeseries.get("timeseries", []):
                    for point in series.get("data", []):
                        avg_clients = point.get("average")
                        if avg_clients is None:
                            continue
                        rows.append({
                            "resource_id": cache["id"].lower(),
                            "resource_name": cache["name"],
                            "timestamp": point["timeStamp"],
                            "avg_connected_clients": float(avg_clients),
                        })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "timestamp": pa.array([], type=pa.string()),
                "avg_connected_clients": pa.array([], type=pa.float64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "timestamp": [r["timestamp"] for r in rows],
            "avg_connected_clients": [r["avg_connected_clients"] for r in rows],
        })
