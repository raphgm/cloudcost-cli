import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# vCPU/memory per Elastic Premium SKU, confirmed via `az functionapp plan
# list-skus` capacity fields and Azure's published EP tier specs.
EP_SKU_SPECS = {
    "EP1": {"vcpu": 1, "memory_gb": 3.5},
    "EP2": {"vcpu": 2, "memory_gb": 7.0},
    "EP3": {"vcpu": 4, "memory_gb": 14.0},
}


# Real check: an Azure Functions Premium (Elastic Premium) plan with a
# minimumElasticInstanceCount > 0 keeps that many pre-warmed instances
# running continuously, billed hourly, whether functions are actually
# invoked or not -- distinct from azure.idle_app_service_plans, which
# only flags a plan with ZERO deployed apps. This check catches a plan
# with real functions deployed but near-zero real execution volume
# while still paying for the reserved minimum floor. "FunctionExecutionCount"
# confirmed via `az monitor metrics list-definitions --resource <plan-id>`.
@registry.register_source("azure.idle_functions_premium_min_instances")
class AzureIdleFunctionsPremiumMinInstancesSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.idle_functions_premium_min_instances requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        plans_raw = subprocess.run(
            ["az", "functionapp", "plan", "list", "--resource-group", self.resource_group,
             "--query", "[?sku.tier=='ElasticPremium'].{id:id,name:name,sku:sku.name,minInstances:sku.capacity}",
             "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        plans = json.loads(plans_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for plan in plans:
            min_instances = plan.get("minInstances", 0) or 0
            if min_instances == 0:
                continue

            apps_raw = subprocess.run(
                ["az", "functionapp", "list", "--resource-group", self.resource_group,
                 "--query", f"[?appServicePlanId=='{plan['id']}'].name", "-o", "json"],
                capture_output=True, text=True, check=True,
            ).stdout
            apps = json.loads(apps_raw)

            total_executions = 0.0
            for app_name in apps:
                app_id_raw = subprocess.run(
                    ["az", "functionapp", "show", "--name", app_name,
                     "--resource-group", self.resource_group, "--query", "id", "-o", "tsv"],
                    capture_output=True, text=True, check=True,
                ).stdout.strip()

                raw = subprocess.run(
                    [
                        "az", "monitor", "metrics", "list",
                        "--resource", app_id_raw,
                        "--metric", "FunctionExecutionCount",
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
                            total_executions += point.get("total") or 0.0

            sku = plan.get("sku", "EP1")
            specs = EP_SKU_SPECS.get(sku, EP_SKU_SPECS["EP1"])
            hourly_price = specs["vcpu"] * 0.173 + specs["memory_gb"] * 0.0123

            rows.append({
                "resource_id": plan["id"].lower(),
                "resource_name": plan["name"],
                "sku": sku,
                "min_instances": min_instances,
                "app_count": len(apps),
                "total_executions": total_executions,
                "hourly_price_per_instance": hourly_price,
                "lookback_days": self.lookback_days,
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "sku": pa.array([], type=pa.string()),
                "min_instances": pa.array([], type=pa.int64()),
                "app_count": pa.array([], type=pa.int64()),
                "total_executions": pa.array([], type=pa.float64()),
                "hourly_price_per_instance": pa.array([], type=pa.float64()),
                "lookback_days": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "sku": [r["sku"] for r in rows],
            "min_instances": [r["min_instances"] for r in rows],
            "app_count": [r["app_count"] for r in rows],
            "total_executions": [r["total_executions"] for r in rows],
            "hourly_price_per_instance": [r["hourly_price_per_instance"] for r in rows],
            "lookback_days": [r["lookback_days"] for r in rows],
        })
