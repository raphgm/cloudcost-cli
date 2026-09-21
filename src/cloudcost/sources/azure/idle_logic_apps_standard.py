import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: Logic Apps Standard (WorkflowStandard/WS-tier) plans
# reserve fixed vCPU/memory, billed hourly whether workflows actually
# run or not -- Consumption-tier Logic Apps are pay-per-action and
# have no equivalent waste. Distinct from azure.idle_app_service_plans
# (zero deployed apps): this catches a plan with a real Logic App
# deployed but near-zero real workflow run activity.
# Real metric name confirmed via the platform's own error message
# (Azure Monitor's metric list for Microsoft.Web/sites): the correct
# name is "WorkflowRunsCompleted", not the more obvious "RunsCompleted".
@registry.register_source("azure.idle_logic_apps_standard")
class AzureIdleLogicAppsStandardSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.idle_logic_apps_standard requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        plans_raw = subprocess.run(
            ["az", "appservice", "plan", "list", "--resource-group", self.resource_group,
             "--query", "[?sku.tier=='WorkflowStandard'].{id:id,name:name,sku:sku.name,capacity:sku.capacity}",
             "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        plans = json.loads(plans_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for plan in plans:
            # Real bug found and fixed: `az logicapp list` exposes the
            # hosting plan under "serverFarmId", not "appServicePlanId"
            # (the latter returns null even though the app clearly runs
            # on the plan) -- confirmed by dumping the full object.
            apps_raw = subprocess.run(
                ["az", "logicapp", "list", "--resource-group", self.resource_group,
                 "--query", f"[?serverFarmId=='{plan['id']}'].{{name:name,id:id}}", "-o", "json"],
                capture_output=True, text=True, check=True,
            ).stdout
            apps = json.loads(apps_raw)

            if not apps:
                continue

            total_runs = 0.0
            for app in apps:
                raw = subprocess.run(
                    [
                        "az", "monitor", "metrics", "list",
                        "--resource", app["id"],
                        "--metric", "WorkflowRunsCompleted",
                        "--aggregation", "Total",
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
                            total_runs += point.get("total") or 0.0

            sku = plan.get("sku", "WS1")
            capacity = plan.get("capacity", 1) or 1
            hourly_price = capacity * (0.1997 + 3.5 * 0.0143)

            rows.append({
                "resource_id": plan["id"].lower(),
                "resource_name": plan["name"],
                "sku": sku,
                "capacity": capacity,
                "app_count": len(apps),
                "total_runs": total_runs,
                "hourly_price": hourly_price,
                "lookback_days": self.lookback_days,
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "sku": pa.array([], type=pa.string()),
                "capacity": pa.array([], type=pa.int64()),
                "app_count": pa.array([], type=pa.int64()),
                "total_runs": pa.array([], type=pa.float64()),
                "hourly_price": pa.array([], type=pa.float64()),
                "lookback_days": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "sku": [r["sku"] for r in rows],
            "capacity": [r["capacity"] for r in rows],
            "app_count": [r["app_count"] for r in rows],
            "total_runs": [r["total_runs"] for r in rows],
            "hourly_price": [r["hourly_price"] for r in rows],
            "lookback_days": [r["lookback_days"] for r in rows],
        })
