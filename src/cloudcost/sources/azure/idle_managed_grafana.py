import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: Azure Managed Grafana (Standard SKU) bills a fixed hourly
# node fee whether anyone opens a dashboard or not -- Essential SKU is
# priced per-user instead and is excluded upstream (no fixed node
# waste). "HttpRequestCount" confirmed via
# `az monitor metrics list-definitions --resource <grafana-id>`.
@registry.register_source("azure.idle_managed_grafana")
class AzureIdleManagedGrafanaSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.idle_managed_grafana requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        instances_raw = subprocess.run(
            ["az", "grafana", "list", "--resource-group", self.resource_group,
             "--query", "[].{id:id,name:name,sku:sku.name}", "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        instances = json.loads(instances_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for instance in instances:
            if instance.get("sku", "").lower() != "standard":
                continue

            raw = subprocess.run(
                [
                    "az", "monitor", "metrics", "list",
                    "--resource", instance["id"],
                    "--metric", "HttpRequestCount",
                    "--aggregation", "Total",
                    "--interval", "PT1H",
                    "--start-time", start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "--end-time", end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ],
                capture_output=True, text=True, check=True,
            ).stdout
            parsed = json.loads(raw)

            total_requests = 0.0
            for timeseries in parsed.get("value", []):
                for series in timeseries.get("timeseries", []):
                    for point in series.get("data", []):
                        total_requests += point.get("total") or 0.0

            rows.append({
                "resource_id": instance["id"].lower(),
                "resource_name": instance["name"],
                "sku": instance.get("sku", "Standard"),
                "total_requests": total_requests,
                "lookback_days": self.lookback_days,
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "sku": pa.array([], type=pa.string()),
                "total_requests": pa.array([], type=pa.float64()),
                "lookback_days": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "sku": [r["sku"] for r in rows],
            "total_requests": [r["total_requests"] for r in rows],
            "lookback_days": [r["lookback_days"] for r in rows],
        })
