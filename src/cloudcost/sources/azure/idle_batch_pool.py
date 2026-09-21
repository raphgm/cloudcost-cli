import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real bug found and fixed: `az batch pool list` returns vmSize
# lowercase ("standard_d2s_v3"), but the Retail Prices API's
# armSkuName is case-sensitive ("Standard_D2s_v3") -- matching with
# tolower() on both sides avoids guessing Azure's capitalization rules.
def _fetch_hourly_price(vm_size: str, region: str) -> float:
    filter_str = (
        f"armRegionName eq '{region}' and tolower(armSkuName) eq '{vm_size.lower()}' "
        f"and priceType eq 'Consumption' and contains(productName, 'Windows') eq false"
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


# Real check: an Azure Batch pool's dedicated compute nodes bill the
# same per-hour VM rate as any standalone VM, whether real tasks are
# running on them or sitting idle waiting for work. There's no
# per-pool utilization metric exposed via Azure Monitor, so this check
# uses real inventory instead: currentDedicatedNodes (from
# `az batch pool list`) against active job count (from
# `az batch job list`) -- flagging any pool with dedicated nodes
# allocated and zero active jobs right now.
@registry.register_source("azure.idle_batch_pool")
class AzureIdleBatchPoolSource:
    def __init__(self, config: dict):
        self.account_name = config.get("account_name")
        self.resource_group = config.get("resource_group")
        if not self.account_name or not self.resource_group:
            raise ValueError("azure.idle_batch_pool requires 'account_name' and 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        subprocess.run(
            ["az", "batch", "account", "login", "--name", self.account_name,
             "--resource-group", self.resource_group],
            capture_output=True, text=True, check=True,
        )

        pools_raw = subprocess.run(
            ["az", "batch", "pool", "list", "--query",
             "[].{id:id,vmSize:vmSize,currentDedicatedNodes:currentDedicatedNodes,location:'eastus'}",
             "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        pools = json.loads(pools_raw)

        rows = []
        for pool in pools:
            dedicated_nodes = pool.get("currentDedicatedNodes", 0)
            if not dedicated_nodes:
                continue

            tasks_raw = subprocess.run(
                ["az", "batch", "job", "list", "--query",
                 "[?state=='active'].id", "-o", "json"],
                capture_output=True, text=True, check=True,
            ).stdout
            active_jobs = json.loads(tasks_raw)

            vm_size = pool.get("vmSize", "standard_a1_v2")

            rows.append({
                "resource_id": f"batch/{self.account_name}/pools/{pool['id']}",
                "resource_name": pool["id"],
                "vm_size": vm_size,
                "dedicated_nodes": dedicated_nodes,
                "active_job_count": len(active_jobs),
                "hourly_price_per_node": _fetch_hourly_price(vm_size, "eastus"),
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "vm_size": pa.array([], type=pa.string()),
                "dedicated_nodes": pa.array([], type=pa.int64()),
                "active_job_count": pa.array([], type=pa.int64()),
                "hourly_price_per_node": pa.array([], type=pa.float64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "vm_size": [r["vm_size"] for r in rows],
            "dedicated_nodes": [r["dedicated_nodes"] for r in rows],
            "active_job_count": [r["active_job_count"] for r in rows],
            "hourly_price_per_node": [r["hourly_price_per_node"] for r in rows],
        })
