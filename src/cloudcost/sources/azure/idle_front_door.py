import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: Azure Front Door (Standard/Premium) charges a fixed
# monthly base fee whether any real traffic passes through it or not --
# $35/month Standard, $412.50/month Premium (Retail Prices API,
# 'Azure Front Door Service' service, '<Tier> Base Fees' meters).
# "RequestCount" confirmed via
# `az monitor metrics list-definitions --resource <afd-profile-id>`.
@registry.register_source("azure.idle_front_door")
class AzureIdleFrontDoorSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.idle_front_door requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        profiles_raw = subprocess.run(
            ["az", "afd", "profile", "list", "--resource-group", self.resource_group,
             "--query", "[].{id:id,name:name,sku:sku.name}", "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        profiles = json.loads(profiles_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for profile in profiles:
            raw = subprocess.run(
                [
                    "az", "monitor", "metrics", "list",
                    "--resource", profile["id"],
                    "--metric", "RequestCount",
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
                "resource_id": profile["id"].lower(),
                "resource_name": profile["name"],
                "sku": profile.get("sku", "Standard_AzureFrontDoor"),
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
