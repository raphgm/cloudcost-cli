import json
import subprocess
from typing import Any, Optional

import pyarrow as pa

from cloudcost.core.registry import registry


def _get_capability(capabilities: list, name: str) -> Optional[str]:
    for cap in capabilities:
        if cap.get("name") == name:
            return cap.get("value")
    return None


def _fetch_sku_specs(region: str) -> list[dict]:
    raw = subprocess.run(
        ["az", "vm", "list-skus", "--location", region, "--resource-type", "virtualMachines", "-o", "json"],
        capture_output=True, text=True, check=True,
    ).stdout
    skus = json.loads(raw)

    specs = []
    for sku in skus:
        caps = sku.get("capabilities", [])
        vcpus = _get_capability(caps, "vCPUs")
        memory_gb = _get_capability(caps, "MemoryGB")
        if vcpus is None or memory_gb is None:
            continue
        specs.append({
            "name": sku["name"],
            "vcpus": int(vcpus),
            "memory_gb": float(memory_gb),
        })
    return specs


def _fetch_live_price_per_hour(sku_name: str, region: str) -> Optional[float]:
    # Real Azure Retail Prices API — no auth required. Picks the Linux
    # consumption meter (Windows meters carry a licensing surcharge that
    # would misrepresent the comparison for a Linux VM).
    filter_expr = (
        f"serviceName eq 'Virtual Machines' and armRegionName eq '{region}' "
        f"and armSkuName eq '{sku_name}' and priceType eq 'Consumption'"
    )
    raw = subprocess.run(
        ["curl", "-s", "https://prices.azure.com/api/retail/prices", "--get", "--data-urlencode", f"$filter={filter_expr}"],
        capture_output=True, text=True, check=True,
    ).stdout
    parsed = json.loads(raw)
    items = parsed.get("Items", [])
    linux_items = [i for i in items if "Windows" not in i.get("productName", "")]
    if not linux_items:
        return None
    return linux_items[0]["retailPrice"]


# Live SKU-downsize recommendation, using Azure's own real, current SKU
# capability data (az vm list-skus) and real, current pricing (Retail
# Prices API) instead of a hardcoded table — a hardcoded SKU-to-price
# lookup goes stale the moment Azure changes a price or ships a new SKU
# family; this doesn't.
@registry.register_source("azure.vm_sizing_recommendation")
class AzureVmSizingRecommendationSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.region = config.get("region", "eastus")

    def extract(self, context: Any = None) -> pa.Table:
        cmd = ["az", "vm", "list", "--query", "[].{id:id,name:name,vmSize:hardwareProfile.vmSize,resourceGroup:resourceGroup}"]
        if self.resource_group:
            cmd += ["--resource-group", self.resource_group]
        vms = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)

        if not vms:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "current_size": pa.array([], type=pa.string()),
                "current_price_per_hour": pa.array([], type=pa.float64()),
                "recommended_size": pa.array([], type=pa.string()),
                "recommended_price_per_hour": pa.array([], type=pa.float64()),
                "estimated_monthly_savings_usd": pa.array([], type=pa.float64()),
            })

        sku_specs = _fetch_sku_specs(self.region)
        specs_by_name = {s["name"]: s for s in sku_specs}

        rows = []
        for vm in vms:
            current_size = vm["vmSize"]
            current_spec = specs_by_name.get(current_size)
            if not current_spec:
                continue

            # A real "just smaller" candidate: same or fewer vCPUs and
            # memory, strictly smaller on at least one, ranked by closeness
            # rather than a fixed family-specific hardcoded successor.
            candidates = [
                s for s in sku_specs
                if s["name"] != current_size
                and s["vcpus"] <= current_spec["vcpus"]
                and s["memory_gb"] <= current_spec["memory_gb"]
                and (s["vcpus"] < current_spec["vcpus"] or s["memory_gb"] < current_spec["memory_gb"])
            ]
            if not candidates:
                continue
            candidates.sort(key=lambda s: (current_spec["vcpus"] - s["vcpus"]) + (current_spec["memory_gb"] - s["memory_gb"]))
            best_candidate = candidates[0]

            current_price = _fetch_live_price_per_hour(current_size, self.region)
            candidate_price = _fetch_live_price_per_hour(best_candidate["name"], self.region)
            if current_price is None or candidate_price is None:
                continue

            monthly_savings = (current_price - candidate_price) * 730
            if monthly_savings <= 0:
                continue

            rows.append({
                "resource_id": vm["id"].lower(),
                "resource_name": vm["name"],
                "current_size": current_size,
                "current_price_per_hour": current_price,
                "recommended_size": best_candidate["name"],
                "recommended_price_per_hour": candidate_price,
                "estimated_monthly_savings_usd": round(monthly_savings, 2),
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "current_size": pa.array([], type=pa.string()),
                "current_price_per_hour": pa.array([], type=pa.float64()),
                "recommended_size": pa.array([], type=pa.string()),
                "recommended_price_per_hour": pa.array([], type=pa.float64()),
                "estimated_monthly_savings_usd": pa.array([], type=pa.float64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "current_size": [r["current_size"] for r in rows],
            "current_price_per_hour": [r["current_price_per_hour"] for r in rows],
            "recommended_size": [r["recommended_size"] for r in rows],
            "recommended_price_per_hour": [r["recommended_price_per_hour"] for r in rows],
            "estimated_monthly_savings_usd": [r["estimated_monthly_savings_usd"] for r in rows],
        })
