import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


def _normalize_region(location: str) -> str:
    return location.lower().replace(" ", "")


def _fetch_hourly_price(sku_name: str, region: str) -> float:
    region = _normalize_region(region)
    filter_str = (
        f"armRegionName eq '{region}' and armSkuName eq '{sku_name}' "
        f"and priceType eq 'Consumption' and contains(productName, 'Azure Data Explorer') eq true"
    )

    try:
        raw = subprocess.run(
            [
                "curl",
                "-s",
                "-G",
                "https://prices.azure.com/api/retail/prices",
                "--data-urlencode",
                f"$filter={filter_str}",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        ).stdout
        data = json.loads(raw)
        items = [
            item
            for item in data.get("Items", [])
            if item.get("unitOfMeasure") == "1 Hour"
            and item.get("skuName") == sku_name
        ]
        return float(items[0]["retailPrice"]) if items else 0.0
    except Exception:
        return 0.0


# Real check: Azure Data Explorer clusters reserve fixed instance counts
# and are billed hourly even when ingestion and query volume is near zero.
# The check is based on live cluster inventory plus zero-ingestion and zero-
# query totals over the lookback window.
@registry.register_source("azure.idle_kusto_cluster")
class AzureIdleKustoClusterSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)

        if not self.resource_group:
            raise ValueError("azure.idle_kusto_cluster requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        clusters_raw = subprocess.run(
            [
                "az",
                "kusto",
                "cluster",
                "list",
                "--resource-group",
                self.resource_group,
                "--query",
                "[].{id:id,name:name,sku:sku,location:location}",
                "-o",
                "json",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        clusters = json.loads(clusters_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for cluster in clusters:
            sku = cluster.get("sku") or {}
            if isinstance(sku, dict):
                sku_name = sku.get("name") or sku.get("skuName") or "unknown"
                instance_count = sku.get("capacity") or 1
            else:
                sku_name = sku
                instance_count = 1

            if sku_name == "unknown":
                continue

            ingestion_raw = subprocess.run(
                [
                    "az",
                    "monitor",
                    "metrics",
                    "list",
                    "--resource",
                    cluster["id"],
                    "--metric",
                    "IngestionVolumeMB",
                    "--aggregation",
                    "Total",
                    "--interval",
                    "PT1H",
                    "--start-time",
                    start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "--end-time",
                    end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            ingestion_parsed = json.loads(ingestion_raw)

            total_ingestion_mb = 0.0
            for timeseries in ingestion_parsed.get("value", []):
                for series in timeseries.get("timeseries", []):
                    for point in series.get("data", []):
                        total_ingestion_mb += point.get("total") or 0.0

            query_raw = subprocess.run(
                [
                    "az",
                    "monitor",
                    "metrics",
                    "list",
                    "--resource",
                    cluster["id"],
                    "--metric",
                    "QueryCount",
                    "--aggregation",
                    "Total",
                    "--interval",
                    "PT1H",
                    "--start-time",
                    start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "--end-time",
                    end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            query_parsed = json.loads(query_raw)

            total_queries = 0.0
            for timeseries in query_parsed.get("value", []):
                for series in timeseries.get("timeseries", []):
                    for point in series.get("data", []):
                        total_queries += point.get("total") or 0.0

            rows.append(
                {
                    "resource_id": cluster["id"].lower(),
                    "resource_name": cluster["name"],
                    "sku": sku_name,
                    "instance_count": instance_count,
                    "total_ingestion_mb": total_ingestion_mb,
                    "total_queries": total_queries,
                    "hourly_price_per_instance": _fetch_hourly_price(
                        sku_name,
                        cluster.get("location", "eastus"),
                    ),
                    "lookback_days": self.lookback_days,
                }
            )

        if not rows:
            return pa.table(
                {
                    "resource_id": pa.array([], type=pa.string()),
                    "resource_name": pa.array([], type=pa.string()),
                    "sku": pa.array([], type=pa.string()),
                    "instance_count": pa.array([], type=pa.int64()),
                    "total_ingestion_mb": pa.array([], type=pa.float64()),
                    "total_queries": pa.array([], type=pa.float64()),
                    "hourly_price_per_instance": pa.array([], type=pa.float64()),
                    "lookback_days": pa.array([], type=pa.int64()),
                }
            )

        return pa.table(
            {
                "resource_id": [r["resource_id"] for r in rows],
                "resource_name": [r["resource_name"] for r in rows],
                "sku": [r["sku"] for r in rows],
                "instance_count": [r["instance_count"] for r in rows],
                "total_ingestion_mb": [r["total_ingestion_mb"] for r in rows],
                "total_queries": [r["total_queries"] for r in rows],
                "hourly_price_per_instance": [r["hourly_price_per_instance"] for r in rows],
                "lookback_days": [r["lookback_days"] for r in rows],
            }
        )
