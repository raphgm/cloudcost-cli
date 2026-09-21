import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real Azure Container Instances check: a container group with
# restartPolicy=Always bills per-second for its requested vCPU/memory
# for as long as it's up, whether it's doing real work or idling.
# "CpuUsage" metric confirmed via
# `az monitor metrics list-definitions --resource <aci-id>`.
@registry.register_source("azure.idle_container_instances")
class AzureIdleContainerInstancesSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.idle_container_instances requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        groups_raw = subprocess.run(
            ["az", "container", "list", "--resource-group", self.resource_group,
             "--query", "[].{id:id,name:name,cpu:containers[0].resources.requests.cpu,memoryGb:containers[0].resources.requests.memoryInGb,restartPolicy:restartPolicy}",
             "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        groups = json.loads(groups_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for grp in groups:
            if grp.get("restartPolicy") != "Always":
                continue

            raw = subprocess.run(
                [
                    "az", "monitor", "metrics", "list",
                    "--resource", grp["id"],
                    "--metric", "CpuUsage",
                    "--aggregation", "Average",
                    "--interval", "PT1H",
                    "--start-time", start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "--end-time", end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ],
                capture_output=True, text=True, check=True,
            ).stdout
            parsed = json.loads(raw)

            avg_values = []
            for timeseries in parsed.get("value", []):
                for series in timeseries.get("timeseries", []):
                    for point in series.get("data", []):
                        if point.get("average") is not None:
                            avg_values.append(point["average"])

            avg_cpu = sum(avg_values) / len(avg_values) if avg_values else 0.0

            rows.append({
                "resource_id": grp["id"].lower(),
                "resource_name": grp["name"],
                "requested_cpu": grp.get("cpu") or 1.0,
                "requested_memory_gb": grp.get("memoryGb") or 1.5,
                "avg_cpu_millicores": avg_cpu,
                "lookback_days": self.lookback_days,
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "requested_cpu": pa.array([], type=pa.float64()),
                "requested_memory_gb": pa.array([], type=pa.float64()),
                "avg_cpu_millicores": pa.array([], type=pa.float64()),
                "lookback_days": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "requested_cpu": [r["requested_cpu"] for r in rows],
            "requested_memory_gb": [r["requested_memory_gb"] for r in rows],
            "avg_cpu_millicores": [r["avg_cpu_millicores"] for r in rows],
            "lookback_days": [r["lookback_days"] for r in rows],
        })
