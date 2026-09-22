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


# Real check: an Azure Machine Learning Compute Instance is a
# single-user interactive dev VM that bills continuously while in the
# "Running" state, whether a notebook kernel is actually active or not.
# AML has an opt-in "idle shutdown" feature (idleTimeBeforeShutdown) --
# a real, commonly-missed setting -- so this flags any Running compute
# instance that doesn't have it configured, using real inventory via
# `az ml compute show` (no CPU metric needed: a data scientist leaving
# a notebook tab open all weekend looks identical to real work in CPU
# terms, but the instance running with no auto-shutdown safety net is
# the real, actionable risk regardless).
@registry.register_source("azure.idle_aml_compute_instance")
class AzureIdleAmlComputeInstanceSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.workspace_name = config.get("workspace_name")
        if not self.resource_group or not self.workspace_name:
            raise ValueError("azure.idle_aml_compute_instance requires 'resource_group' and 'workspace_name' in config")

    def extract(self, context: Any = None) -> pa.Table:
        computes_raw = subprocess.run(
            ["az", "ml", "compute", "list", "--resource-group", self.resource_group,
             "--workspace-name", self.workspace_name, "--type", "ComputeInstance",
             "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        computes = json.loads(computes_raw)

        rows = []
        for compute in computes:
            if compute.get("state") != "Running":
                continue

            idle_shutdown = compute.get("idle_time_before_shutdown_minutes")
            if idle_shutdown:
                continue

            vm_size = compute.get("size", "Standard_DS3_v2")
            region = compute.get("location", "eastus").lower().replace(" ", "")

            rows.append({
                "resource_id": f"{self.workspace_name}/computes/{compute['name']}",
                "resource_name": compute["name"],
                "vm_size": vm_size,
                "state": compute.get("state", "unknown"),
                "hourly_price": _fetch_hourly_price(vm_size, region),
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "vm_size": pa.array([], type=pa.string()),
                "state": pa.array([], type=pa.string()),
                "hourly_price": pa.array([], type=pa.float64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "vm_size": [r["vm_size"] for r in rows],
            "state": [r["state"] for r in rows],
            "hourly_price": [r["hourly_price"] for r in rows],
        })
