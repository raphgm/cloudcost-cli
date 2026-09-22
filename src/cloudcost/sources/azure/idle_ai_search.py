import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: Azure AI Search (Cognitive Search) reserves fixed
# replica/partition compute at a per-tier hourly rate, billed
# whether real queries hit it or not -- Free tier is $0 and excluded
# upstream. "SearchQueriesPerSecond" confirmed via
# `az monitor metrics list-definitions --resource <search-id>`.
BASE_HOURLY_PRICE = {
    "basic": 0.101,
    "standard": 0.348,
    "standard2": 1.344,
    "standard3": 2.688,
}


@registry.register_source("azure.idle_ai_search")
class AzureIdleAiSearchSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.idle_ai_search requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        services_raw = subprocess.run(
            ["az", "search", "service", "list", "--resource-group", self.resource_group,
             "--query", "[].{id:id,name:name,sku:sku.name,replicaCount:replicaCount,partitionCount:partitionCount}",
             "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        services = json.loads(services_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for svc in services:
            tier = svc.get("sku", "basic")
            if tier not in BASE_HOURLY_PRICE:
                continue

            raw = subprocess.run(
                [
                    "az", "monitor", "metrics", "list",
                    "--resource", svc["id"],
                    "--metric", "SearchQueriesPerSecond",
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

            avg_qps = sum(avg_values) / len(avg_values) if avg_values else 0.0
            replicas = svc.get("replicaCount", 1) or 1
            partitions = svc.get("partitionCount", 1) or 1

            rows.append({
                "resource_id": svc["id"].lower(),
                "resource_name": svc["name"],
                "tier": tier,
                "replicas": replicas,
                "partitions": partitions,
                "avg_queries_per_second": avg_qps,
                "hourly_price_per_unit": BASE_HOURLY_PRICE.get(tier, 0.0),
                "lookback_days": self.lookback_days,
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "tier": pa.array([], type=pa.string()),
                "replicas": pa.array([], type=pa.int64()),
                "partitions": pa.array([], type=pa.int64()),
                "avg_queries_per_second": pa.array([], type=pa.float64()),
                "hourly_price_per_unit": pa.array([], type=pa.float64()),
                "lookback_days": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "tier": [r["tier"] for r in rows],
            "replicas": [r["replicas"] for r in rows],
            "partitions": [r["partitions"] for r in rows],
            "avg_queries_per_second": [r["avg_queries_per_second"] for r in rows],
            "hourly_price_per_unit": [r["hourly_price_per_unit"] for r in rows],
            "lookback_days": [r["lookback_days"] for r in rows],
        })
