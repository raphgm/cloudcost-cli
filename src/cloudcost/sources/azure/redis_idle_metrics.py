import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real bug found and fixed: the policy used to hardcode the Basic C0
# price ($0.022/hr) for every Redis instance regardless of its real
# tier/SKU -- badly underpricing Standard/Premium findings. Now fetches
# the live price for the cache's actual "<Tier> <Family><Capacity>"
# SKU (e.g. "Standard C1", "Premium P2") via the Retail Prices API,
# same live-pricing approach used elsewhere in this project.
def _normalize_region(location: str) -> str:
    # Same real bug as postgres_idle_flexible.py / mysql_idle_flexible.py:
    # az returns display form ("East US"), Retail Prices API needs
    # compact form ("eastus").
    return location.lower().replace(" ", "")


def _fetch_hourly_price(tier: str, family: str, capacity: int, region: str) -> float:
    sku_name = f"{family}{capacity}"
    region = _normalize_region(region)
    filter_str = (
        f"armRegionName eq '{region}' and serviceName eq 'Redis Cache' "
        f"and skuName eq '{sku_name}' and contains(productName, '{tier}')"
    )
    try:
        raw = subprocess.run(
            ["curl", "-s", "-G", "https://prices.azure.com/api/retail/prices",
             "--data-urlencode", f"$filter={filter_str}"],
            capture_output=True, text=True, check=True, timeout=15,
        ).stdout
        data = json.loads(raw)
        items = [i for i in data.get("Items", []) if i.get("unitOfMeasure") == "1 Hour"]
        return items[0]["retailPrice"] if items else 0.0
    except Exception:
        return 0.0


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
            ["az", "redis", "list", "--resource-group", self.resource_group,
             "--query", "[].{id:id,name:name,tier:sku.name,family:sku.family,capacity:sku.capacity,location:location}",
             "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        caches = json.loads(caches_raw)
        cache_prices = {
            c["id"].lower(): _fetch_hourly_price(c["tier"], c["family"], c["capacity"], c["location"])
            for c in caches
        }

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
                            "hourly_price": cache_prices.get(cache["id"].lower(), 0.0),
                        })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "timestamp": pa.array([], type=pa.string()),
                "avg_connected_clients": pa.array([], type=pa.float64()),
                "hourly_price": pa.array([], type=pa.float64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "timestamp": [r["timestamp"] for r in rows],
            "avg_connected_clients": [r["avg_connected_clients"] for r in rows],
            "hourly_price": [r["hourly_price"] for r in rows],
        })
