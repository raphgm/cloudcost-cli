import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


def _normalize_region(location: str) -> str:
    # Real bug found and fixed: `az postgres flexible-server list`
    # returns location in display form ("North Europe"), but the
    # Retail Prices API's armRegionName needs the compact form
    # ("northeurope") -- lowercase, no spaces.
    return location.lower().replace(" ", "")


# Real check: Azure Database for PostgreSQL Flexible Server bills its
# provisioned vCore/tier hourly regardless of connections or CPU used --
# distinct service from azure.sql_dtu_metrics (Azure SQL DB, DTU-based).
# "cpu_percent" confirmed via
# `az monitor metrics list-definitions --resource <server-id>`.
def _fetch_hourly_price(sku_name: str, region: str) -> float:
    # sku_name arrives like "Standard_B1ms" -- the Retail Prices API
    # meter uses the bare size in uppercase (e.g. "B1MS").
    bare_size = sku_name.replace("Standard_", "").upper()
    filter_str = (
        f"armRegionName eq '{region}' and contains(productName, 'PostgreSQL Flexible Server') "
        f"and contains(meterName, '{bare_size}')"
    )
    try:
        raw = subprocess.run(
            ["curl", "-s", "-G", "https://prices.azure.com/api/retail/prices",
             "--data-urlencode", f"$filter={filter_str}"],
            capture_output=True, text=True, check=True, timeout=15,
        ).stdout
        data = json.loads(raw)
        items = [
            i for i in data.get("Items", [])
            if i.get("unitOfMeasure") == "1 Hour" and i["meterName"].endswith(bare_size)
        ]
        return items[0]["retailPrice"] if items else 0.0
    except Exception:
        return 0.0


@registry.register_source("azure.postgres_idle_flexible")
class AzurePostgresIdleFlexibleSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.postgres_idle_flexible requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        servers_raw = subprocess.run(
            ["az", "postgres", "flexible-server", "list", "--resource-group", self.resource_group,
             "--query", "[].{id:id,name:name,sku:sku.name,location:location}", "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        servers = json.loads(servers_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for server in servers:
            raw = subprocess.run(
                [
                    "az", "monitor", "metrics", "list",
                    "--resource", server["id"],
                    "--metric", "cpu_percent",
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
            sku_name = server.get("sku", "Standard_B1ms")

            rows.append({
                "resource_id": server["id"].lower(),
                "resource_name": server["name"],
                "sku_name": sku_name,
                "avg_cpu_percent": avg_cpu,
                "hourly_price": _fetch_hourly_price(sku_name, _normalize_region(server.get("location", "eastus"))),
                "lookback_days": self.lookback_days,
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "sku_name": pa.array([], type=pa.string()),
                "avg_cpu_percent": pa.array([], type=pa.float64()),
                "hourly_price": pa.array([], type=pa.float64()),
                "lookback_days": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "sku_name": [r["sku_name"] for r in rows],
            "avg_cpu_percent": [r["avg_cpu_percent"] for r in rows],
            "hourly_price": [r["hourly_price"] for r in rows],
            "lookback_days": [r["lookback_days"] for r in rows],
        })
