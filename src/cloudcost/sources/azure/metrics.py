import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real Azure Monitor CPU utilization, via the Azure CLI's own authenticated
# session (az monitor metrics list) — the same auth pattern as azure.cost_export.
# This is what allows a rightsizing policy to be a genuine measurement
# instead of the "we simulate a finding" placeholder zero_utilization.sql
# shipped with before this: cost data alone can tell you a VM is expensive,
# never whether it's actually being used.
@registry.register_source("azure.vm_metrics")
class AzureVmMetricsSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 1)
        if not self.resource_group:
            raise ValueError("azure.vm_metrics requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        subscription_id = subprocess.run(
            ["az", "account", "show", "--query", "id", "-o", "tsv"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

        vm_ids_raw = subprocess.run(
            ["az", "vm", "list", "--resource-group", self.resource_group, "--query", "[].id", "-o", "tsv"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        vm_ids = [v for v in vm_ids_raw.splitlines() if v]

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for vm_id in vm_ids:
            raw = subprocess.run(
                [
                    "az", "monitor", "metrics", "list",
                    "--resource", vm_id,
                    "--metric", "Percentage CPU",
                    "--aggregation", "Average",
                    "--interval", "PT1H",
                    "--start-time", start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "--end-time", end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ],
                capture_output=True, text=True, check=True,
            ).stdout
            parsed = json.loads(raw)

            vm_name = vm_id.split("/")[-1]
            for timeseries in parsed.get("value", []):
                for series in timeseries.get("timeseries", []):
                    for point in series.get("data", []):
                        avg_cpu = point.get("average")
                        if avg_cpu is None:
                            continue
                        rows.append({
                            "resource_id": vm_id.lower(),
                            "resource_name": vm_name,
                            "timestamp": point["timeStamp"],
                            "avg_cpu_percent": float(avg_cpu),
                        })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "timestamp": pa.array([], type=pa.string()),
                "avg_cpu_percent": pa.array([], type=pa.float64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "timestamp": [r["timestamp"] for r in rows],
            "avg_cpu_percent": [r["avg_cpu_percent"] for r in rows],
        })
