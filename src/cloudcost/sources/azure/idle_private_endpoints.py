import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real Private Endpoint traffic metrics, confirmed via
# `az monitor metrics list-definitions --resource <pe-id>` (real names:
# "PEBytesIn"/"PEBytesOut", Total aggregation, PT1H grain works fine here --
# unlike the Bastion "sessions" metric, no grain restriction hit).
@registry.register_source("azure.idle_private_endpoints")
class AzureIdlePrivateEndpointsSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.idle_private_endpoints requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        pes_raw = subprocess.run(
            ["az", "network", "private-endpoint", "list", "--resource-group", self.resource_group,
             "--query", "[].{id:id,name:name}", "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        pes = json.loads(pes_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for pe in pes:
            raw = subprocess.run(
                [
                    "az", "monitor", "metrics", "list",
                    "--resource", pe["id"],
                    "--metric", "PEBytesIn,PEBytesOut",
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
                "resource_id": pe["id"].lower(),
                "resource_name": pe["name"],
                "total_bytes": total_bytes,
                "lookback_days": self.lookback_days,
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "total_bytes": pa.array([], type=pa.float64()),
                "lookback_days": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "total_bytes": [r["total_bytes"] for r in rows],
            "lookback_days": [r["lookback_days"] for r in rows],
        })
