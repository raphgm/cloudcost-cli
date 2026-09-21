import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real bug fix reused: Python's stdlib urllib fails TLS verification on
# this machine (see aks_idle_nodepool.py) -- use curl via subprocess.
def _fetch_hourly_price(vm_size: str, region: str) -> float:
    filter_str = (
        f"armRegionName eq '{region}' and armSkuName eq '{vm_size}' "
        f"and priceType eq 'Consumption' and contains(productName, 'Windows') eq false"
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
            if i.get("unitOfMeasure") == "1 Hour"
            and "spot" not in i.get("skuName", "").lower()
            and "low priority" not in i.get("skuName", "").lower()
        ]
        return items[0]["retailPrice"] if items else 0.0
    except Exception:
        return 0.0


# Real check: a VMSS's own instance count (not an autoscale min-floor,
# just the fixed capacity a manual-mode scale set is pinned to) reserves
# that many VMs continuously. If the whole set runs at sustained low CPU,
# the fixed instance count itself is the waste -- distinct from
# azure.vm_sizing (right-sizing a single VM's SKU) and
# azure.aks_idle_nodepool (AKS-managed VMSS). "Percentage CPU" confirmed
# via `az monitor metrics list-definitions --resource <vmss-id>`.
@registry.register_source("azure.idle_vmss")
class AzureIdleVmssSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.idle_vmss requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        vmss_raw = subprocess.run(
            ["az", "vmss", "list", "--resource-group", self.resource_group,
             "--query", "[].{id:id,name:name,capacity:sku.capacity,vmSize:sku.name}", "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        vmss_list = json.loads(vmss_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for vmss in vmss_list:
            raw = subprocess.run(
                [
                    "az", "monitor", "metrics", "list",
                    "--resource", vmss["id"],
                    "--metric", "Percentage CPU",
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
            vm_size = vmss.get("vmSize", "unknown")

            rows.append({
                "resource_id": vmss["id"].lower(),
                "resource_name": vmss["name"],
                "vm_size": vm_size,
                "instance_count": vmss.get("capacity", 1),
                "avg_cpu_percent": avg_cpu,
                "hourly_price_per_instance": _fetch_hourly_price(vm_size, "eastus"),
                "lookback_days": self.lookback_days,
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "vm_size": pa.array([], type=pa.string()),
                "instance_count": pa.array([], type=pa.int64()),
                "avg_cpu_percent": pa.array([], type=pa.float64()),
                "hourly_price_per_instance": pa.array([], type=pa.float64()),
                "lookback_days": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "vm_size": [r["vm_size"] for r in rows],
            "instance_count": [r["instance_count"] for r in rows],
            "avg_cpu_percent": [r["avg_cpu_percent"] for r in rows],
            "hourly_price_per_instance": [r["hourly_price_per_instance"] for r in rows],
            "lookback_days": [r["lookback_days"] for r in rows],
        })
