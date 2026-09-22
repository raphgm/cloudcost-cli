import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: Azure OpenAI deployments on a Provisioned Throughput (PTU)
# SKU reserve fixed capacity billed hourly regardless of real token
# volume -- distinct from Standard/GlobalStandard deployments, which
# are pay-per-token and have no equivalent waste (idle usage there
# already costs $0, same reasoning as serverless Cosmos DB elsewhere in
# this project). "TotalTokens" confirmed via
# `az monitor metrics list-definitions --resource <account-id>`.
PROVISIONED_SKU_PREFIXES = ("ProvisionedManaged", "GlobalProvisionedManaged", "DataZoneProvisionedManaged")


@registry.register_source("azure.idle_openai_ptu")
class AzureIdleOpenAIPTUSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.idle_openai_ptu requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        accounts_raw = subprocess.run(
            ["az", "cognitiveservices", "account", "list", "--resource-group", self.resource_group,
             "--query", "[?kind=='OpenAI'].{id:id,name:name}", "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        accounts = json.loads(accounts_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for account in accounts:
            deployments_raw = subprocess.run(
                ["az", "cognitiveservices", "account", "deployment", "list",
                 "--name", account["name"], "--resource-group", self.resource_group,
                 "--query", "[].{name:name,sku:sku.name,capacity:sku.capacity,model:properties.model.name}",
                 "-o", "json"],
                capture_output=True, text=True, check=True,
            ).stdout
            deployments = json.loads(deployments_raw)

            for deployment in deployments:
                sku = deployment.get("sku", "")
                if sku not in PROVISIONED_SKU_PREFIXES:
                    continue

                raw = subprocess.run(
                    [
                        "az", "monitor", "metrics", "list",
                        "--resource", account["id"],
                        "--metric", "TotalTokens",
                        "--aggregation", "Total",
                        "--interval", "PT1H",
                        "--filter", f"ModelDeploymentName eq '{deployment['name']}'",
                        "--start-time", start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "--end-time", end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    ],
                    capture_output=True, text=True, check=True,
                ).stdout
                parsed = json.loads(raw)

                total_tokens = 0.0
                for timeseries in parsed.get("value", []):
                    for series in timeseries.get("timeseries", []):
                        for point in series.get("data", []):
                            total_tokens += point.get("total") or 0.0

                rows.append({
                    "resource_id": f"{account['id'].lower()}/deployments/{deployment['name']}",
                    "resource_name": f"{account['name']}/{deployment['name']}",
                    "model": deployment.get("model", "unknown"),
                    "sku": sku,
                    "ptu_capacity": deployment.get("capacity", 0) or 0,
                    "total_tokens": total_tokens,
                    "lookback_days": self.lookback_days,
                })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "model": pa.array([], type=pa.string()),
                "sku": pa.array([], type=pa.string()),
                "ptu_capacity": pa.array([], type=pa.int64()),
                "total_tokens": pa.array([], type=pa.float64()),
                "lookback_days": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "model": [r["model"] for r in rows],
            "sku": [r["sku"] for r in rows],
            "ptu_capacity": [r["ptu_capacity"] for r in rows],
            "total_tokens": [r["total_tokens"] for r in rows],
            "lookback_days": [r["lookback_days"] for r in rows],
        })
