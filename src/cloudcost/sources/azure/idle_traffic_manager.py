import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: a Traffic Manager profile has no fixed base fee, but each
# monitored endpoint bills a real health-check fee ($0.36/month per
# Azure endpoint, $0.54/month per non-Azure endpoint -- Retail Prices
# API, 'Traffic Manager' service) whether real DNS queries ever route to
# it or not. "QpsByEndpoint" confirmed via
# `az monitor metrics list-definitions --resource <profile-id>`.
@registry.register_source("azure.idle_traffic_manager")
class AzureIdleTrafficManagerSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.idle_traffic_manager requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        profiles_raw = subprocess.run(
            ["az", "network", "traffic-manager", "profile", "list",
             "--resource-group", self.resource_group,
             "--query", "[].{id:id,name:name,endpoints:endpoints}", "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        profiles = json.loads(profiles_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for profile in profiles:
            endpoints = profile.get("endpoints") or []
            if not endpoints:
                continue

            raw = subprocess.run(
                [
                    "az", "monitor", "metrics", "list",
                    "--resource", profile["id"],
                    "--metric", "QpsByEndpoint",
                    "--aggregation", "Total",
                    "--interval", "PT1H",
                    "--start-time", start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "--end-time", end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ],
                capture_output=True, text=True, check=True,
            ).stdout
            parsed = json.loads(raw)

            total_queries = 0.0
            for timeseries in parsed.get("value", []):
                for series in timeseries.get("timeseries", []):
                    for point in series.get("data", []):
                        total_queries += point.get("total") or 0.0

            azure_endpoints = sum(1 for e in endpoints if e.get("type", "").endswith("azureEndpoints"))
            non_azure_endpoints = len(endpoints) - azure_endpoints

            rows.append({
                "resource_id": profile["id"].lower(),
                "resource_name": profile["name"],
                "azure_endpoint_count": azure_endpoints,
                "non_azure_endpoint_count": non_azure_endpoints,
                "total_queries": total_queries,
                "lookback_days": self.lookback_days,
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "azure_endpoint_count": pa.array([], type=pa.int64()),
                "non_azure_endpoint_count": pa.array([], type=pa.int64()),
                "total_queries": pa.array([], type=pa.float64()),
                "lookback_days": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "azure_endpoint_count": [r["azure_endpoint_count"] for r in rows],
            "non_azure_endpoint_count": [r["non_azure_endpoint_count"] for r in rows],
            "total_queries": [r["total_queries"] for r in rows],
            "lookback_days": [r["lookback_days"] for r in rows],
        })
