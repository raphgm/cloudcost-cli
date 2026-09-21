import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: Static Web Apps Standard tier bills a flat $9/month per
# app whether it gets real traffic or not -- Free tier is $0 and
# excluded upstream. "SiteHits" confirmed via
# `az monitor metrics list-definitions --resource <swa-id>`.
@registry.register_source("azure.idle_static_web_app")
class AzureIdleStaticWebAppSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.idle_static_web_app requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        apps_raw = subprocess.run(
            ["az", "staticwebapp", "list", "--resource-group", self.resource_group,
             "--query", "[].{id:id,name:name,sku:sku.name}", "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        apps = json.loads(apps_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for app in apps:
            if app.get("sku", "").lower() != "standard":
                continue

            raw = subprocess.run(
                [
                    "az", "monitor", "metrics", "list",
                    "--resource", app["id"],
                    "--metric", "SiteHits",
                    "--aggregation", "Total",
                    "--interval", "PT1H",
                    "--start-time", start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "--end-time", end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ],
                capture_output=True, text=True, check=True,
            ).stdout
            parsed = json.loads(raw)

            total_hits = 0.0
            for timeseries in parsed.get("value", []):
                for series in timeseries.get("timeseries", []):
                    for point in series.get("data", []):
                        total_hits += point.get("total") or 0.0

            rows.append({
                "resource_id": app["id"].lower(),
                "resource_name": app["name"],
                "sku": app.get("sku", "Standard"),
                "total_hits": total_hits,
                "lookback_days": self.lookback_days,
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "sku": pa.array([], type=pa.string()),
                "total_hits": pa.array([], type=pa.float64()),
                "lookback_days": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "sku": [r["sku"] for r in rows],
            "total_hits": [r["total_hits"] for r in rows],
            "lookback_days": [r["lookback_days"] for r in rows],
        })
