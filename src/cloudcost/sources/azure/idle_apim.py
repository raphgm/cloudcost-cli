import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: Azure API Management instances bill a fixed hourly rate
# per gateway unit for the reserved tier, whether real API calls are
# made or not -- Consumption tier is pay-per-call and has no equivalent
# waste, so it's excluded upstream. Price fetched live per real tier via
# the Retail Prices API (a prior version of this check hardcoded a flat
# $30/month for every tier, which was wrong by 3x-65x depending on
# tier -- real Developer is $0.0658/hr, Basic $0.2016/hr, Standard
# $0.9407/hr, confirmed live). "Requests" metric confirmed via
# `az monitor metrics list-definitions --resource <apim-id>`.
def _fetch_hourly_price(sku: str, region: str) -> float:
    if sku == "Consumption":
        return 0.0
    filter_str = (
        f"armRegionName eq '{region}' and serviceName eq 'API Management' "
        f"and meterName eq '{sku} Unit'"
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


@registry.register_source("azure.idle_apim")
class AzureIdleApimSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.idle_apim requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        services_raw = subprocess.run(
            ["az", "apim", "list", "--resource-group", self.resource_group,
             "--query", "[].{id:id,name:name,sku:sku.name,capacity:sku.capacity,location:location}",
             "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        services = json.loads(services_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for svc in services:
            sku = svc.get("sku", "Developer")
            if sku == "Consumption":
                continue

            raw = subprocess.run(
                [
                    "az", "monitor", "metrics", "list",
                    "--resource", svc["id"],
                    "--metric", "Requests",
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

            region = svc.get("location", "eastus").lower().replace(" ", "")
            unit_count = svc.get("capacity", 1) or 1

            rows.append({
                "resource_id": svc["id"].lower(),
                "resource_name": svc["name"],
                "sku": sku,
                "unit_count": unit_count,
                "total_requests": total_requests,
                "hourly_price_per_unit": _fetch_hourly_price(sku, region),
                "lookback_days": self.lookback_days,
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "sku": pa.array([], type=pa.string()),
                "unit_count": pa.array([], type=pa.int64()),
                "total_requests": pa.array([], type=pa.float64()),
                "hourly_price_per_unit": pa.array([], type=pa.float64()),
                "lookback_days": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "sku": [r["sku"] for r in rows],
            "unit_count": [r["unit_count"] for r in rows],
            "total_requests": [r["total_requests"] for r in rows],
            "hourly_price_per_unit": [r["hourly_price_per_unit"] for r in rows],
            "lookback_days": [r["lookback_days"] for r in rows],
        })
