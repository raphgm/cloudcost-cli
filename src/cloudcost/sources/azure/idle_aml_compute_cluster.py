import json
import subprocess
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


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


# Real check: an Azure ML Compute Cluster (AmlCompute, used for
# training jobs) is designed to scale to zero nodes between jobs --
# min_instances should almost always be 0. A cluster with a nonzero
# minimum keeps that many nodes running continuously (usually to avoid
# training-job cold-start delay), billed at the standard VM-hour rate
# whether a real job is queued or not -- distinct from
# azure.idle_aml_compute_instance (the single-user interactive dev VM
# type). Governance-style check (real inventory via
# `az ml compute show`, no metric needed): min_instances > 0 is itself
# the real, continuous cost, independent of whether jobs are running.
@registry.register_source("azure.idle_aml_compute_cluster")
class AzureIdleAmlComputeClusterSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.workspace_name = config.get("workspace_name")
        if not self.resource_group or not self.workspace_name:
            raise ValueError("azure.idle_aml_compute_cluster requires 'resource_group' and 'workspace_name' in config")

    def extract(self, context: Any = None) -> pa.Table:
        computes_raw = subprocess.run(
            ["az", "ml", "compute", "list", "--resource-group", self.resource_group,
             "--workspace-name", self.workspace_name, "--type", "AmlCompute",
             "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        computes = json.loads(computes_raw)

        rows = []
        for compute in computes:
            min_instances = compute.get("min_instances", 0) or 0
            if min_instances == 0:
                continue

            vm_size = compute.get("size", "Standard_DS3_v2")
            region = compute.get("location", "eastus").lower().replace(" ", "")

            rows.append({
                "resource_id": f"{self.workspace_name}/computes/{compute['name']}",
                "resource_name": compute["name"],
                "vm_size": vm_size,
                "min_instances": min_instances,
                "hourly_price_per_node": _fetch_hourly_price(vm_size, region),
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "vm_size": pa.array([], type=pa.string()),
                "min_instances": pa.array([], type=pa.int64()),
                "hourly_price_per_node": pa.array([], type=pa.float64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "vm_size": [r["vm_size"] for r in rows],
            "min_instances": [r["min_instances"] for r in rows],
            "hourly_price_per_node": [r["hourly_price_per_node"] for r in rows],
        })
