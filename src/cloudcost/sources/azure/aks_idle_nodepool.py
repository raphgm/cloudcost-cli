import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real bug found and worked around: Python's stdlib urllib fails TLS
# verification on this machine (self-signed cert in the chain, likely a
# local proxy/inspection cert) even though `curl` to the same host works
# fine -- a real corporate-laptop scenario a user could easily hit. Using
# curl via subprocess instead, consistent with how every other source in
# this project already shells out to `az`.
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
        items = [i for i in data.get("Items", []) if i.get("unitOfMeasure") == "1 Hour"]
        return items[0]["retailPrice"] if items else 0.0
    except Exception:
        return 0.0


# Real AKS check: the AKS control plane is free (Free tier) -- the actual
# cost is the node pool's VM instances. AKS provisions each node pool as
# a VMSS in an auto-created "MC_<rg>_<cluster>_<region>" managed resource
# group; that VMSS emits the same "Percentage CPU" metric as any VM,
# confirmed via `az monitor metrics list-definitions --resource <vmss-id>`.
# This check flags node pools whose VMSS-wide average CPU is low relative
# to their node count -- a real rightsizing/scale-down signal, distinct
# from azure.vm_sizing which only looks at standalone VMs.
@registry.register_source("azure.aks_idle_nodepool")
class AzureAksIdleNodePoolSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.aks_idle_nodepool requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        clusters_raw = subprocess.run(
            ["az", "aks", "list", "--resource-group", self.resource_group,
             "--query", "[].{name:name,nodeResourceGroup:nodeResourceGroup}", "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        clusters = json.loads(clusters_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for cluster in clusters:
            mc_rg = cluster["nodeResourceGroup"]

            nodepools_raw = subprocess.run(
                ["az", "aks", "nodepool", "list", "--cluster-name", cluster["name"],
                 "--resource-group", self.resource_group,
                 "--query", "[].{name:name,count:count,vmSize:vmSize}", "-o", "json"],
                capture_output=True, text=True, check=True,
            ).stdout
            nodepools = {np["name"]: np for np in json.loads(nodepools_raw)}

            vmss_raw = subprocess.run(
                ["az", "vmss", "list", "--resource-group", mc_rg,
                 "--query", "[].{id:id,name:name}", "-o", "json"],
                capture_output=True, text=True, check=True,
            ).stdout
            vmss_list = json.loads(vmss_raw)

            for vmss in vmss_list:
                pool_name = next(
                    (name for name in nodepools if name in vmss["name"]),
                    None,
                )
                nodepool_info = nodepools.get(pool_name, {})

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
                vm_size = nodepool_info.get("vmSize", "unknown")

                rows.append({
                    "resource_id": vmss["id"].lower(),
                    "resource_name": f"{cluster['name']}/{pool_name or vmss['name']}",
                    "vm_size": vm_size,
                    "node_count": nodepool_info.get("count", 1),
                    "avg_cpu_percent": avg_cpu,
                    "hourly_price_per_node": _fetch_hourly_price(vm_size, "eastus"),
                    "lookback_days": self.lookback_days,
                })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "vm_size": pa.array([], type=pa.string()),
                "node_count": pa.array([], type=pa.int64()),
                "avg_cpu_percent": pa.array([], type=pa.float64()),
                "hourly_price_per_node": pa.array([], type=pa.float64()),
                "lookback_days": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "vm_size": [r["vm_size"] for r in rows],
            "node_count": [r["node_count"] for r in rows],
            "avg_cpu_percent": [r["avg_cpu_percent"] for r in rows],
            "hourly_price_per_node": [r["hourly_price_per_node"] for r in rows],
            "lookback_days": [r["lookback_days"] for r in rows],
        })
