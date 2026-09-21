import json
import subprocess
from typing import Any, Optional

import pyarrow as pa

from cloudcost.core.registry import registry

# Azure's real disk-size-to-tier-letter table (P for Premium SSD, E for
# Standard SSD) -- same GB size maps to the same tier number across both
# families, confirmed against real Retail Prices API results (P6/E6 both
# map to 64GB).
SIZE_TO_TIER_NUMBER = {
    4: 1, 8: 2, 16: 3, 32: 4, 64: 6, 128: 10, 256: 15,
    512: 20, 1024: 30, 2048: 40, 4096: 50, 8192: 60, 16384: 70, 32767: 80,
}


def _closest_tier_number(size_gb: int) -> Optional[int]:
    for boundary in sorted(SIZE_TO_TIER_NUMBER):
        if size_gb <= boundary:
            return SIZE_TO_TIER_NUMBER[boundary]
    return None


def _fetch_disk_price(tier_letter: str, tier_number: int, region: str) -> Optional[float]:
    meter_name = f"{tier_letter}{tier_number} LRS Disk"
    filter_expr = (
        f"serviceName eq 'Storage' and armRegionName eq '{region}' "
        f"and meterName eq '{meter_name}' and priceType eq 'Consumption'"
    )
    raw = subprocess.run(
        ["curl", "-s", "https://prices.azure.com/api/retail/prices", "--get", "--data-urlencode", f"$filter={filter_expr}"],
        capture_output=True, text=True, check=True,
    ).stdout
    items = json.loads(raw).get("Items", [])
    matches = [i for i in items if tier_letter == "P" and "SSD" in i.get("productName", "") or tier_letter == "E"]
    return matches[0]["retailPrice"] if matches else None


# Real check: Premium SSD disks under 256GB that could downsize to
# Standard SSD, using real, current pricing (Retail Prices API) instead
# of a hardcoded table -- the same live-data principle as
# vm_sizing_recommendation.py, applied to disks. This is the specific
# check the competing vuhp/cloud-cost-cli project already has (with a
# hardcoded threshold), that this project was missing until now.
@registry.register_source("azure.premium_disk_downsize")
class AzurePremiumDiskDownsizeSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.region = config.get("region", "eastus")

    def extract(self, context: Any = None) -> pa.Table:
        cmd = ["az", "disk", "list", "--query",
               "[?sku.name=='Premium_LRS'].{id:id,name:name,resourceGroup:resourceGroup,sizeGb:diskSizeGB}"]
        if self.resource_group:
            cmd += ["--resource-group", self.resource_group]
        disks = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)

        rows = []
        for disk in disks:
            size_gb = disk["sizeGb"]
            if size_gb >= 256:
                continue  # matches the competing project's threshold: only flag smaller disks

            tier_number = _closest_tier_number(size_gb)
            if tier_number is None:
                continue

            premium_price = _fetch_disk_price("P", tier_number, self.region)
            standard_price = _fetch_disk_price("E", tier_number, self.region)
            if premium_price is None or standard_price is None:
                continue

            savings = premium_price - standard_price
            if savings <= 5:  # matches the competing project's minimum-savings threshold
                continue

            rows.append({
                "resource_id": disk["id"].lower(),
                "resource_name": disk["name"],
                "resource_group": disk["resourceGroup"],
                "size_gb": size_gb,
                "premium_price_per_month": premium_price,
                "standard_ssd_price_per_month": standard_price,
                "estimated_monthly_savings_usd": round(savings, 2),
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "resource_group": pa.array([], type=pa.string()),
                "size_gb": pa.array([], type=pa.int64()),
                "premium_price_per_month": pa.array([], type=pa.float64()),
                "standard_ssd_price_per_month": pa.array([], type=pa.float64()),
                "estimated_monthly_savings_usd": pa.array([], type=pa.float64()),
            })

        return pa.table({c: [r[c] for r in rows] for c in rows[0].keys()})
