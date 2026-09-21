import json
import subprocess
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


def _normalize_region(location: str) -> str:
    # Same real bug as postgres_idle_flexible.py / redis_idle_metrics.py:
    # az returns display form ("East US"), Retail Prices API needs
    # compact form ("eastus").
    return location.lower().replace(" ", "")


# Real, systemic bug found while building this fix and confirmed present
# in every other source in this project using this same pattern
# (vm_sizing.py, aks_idle_nodepool.py, idle_vmss.py, idle_batch_pool.py):
# the Retail Prices API returns Spot and Low Priority meters alongside
# the standard pay-as-you-go one for the same armSkuName (e.g.
# Standard_D16s_v5 Spot at $0.162/hr vs the real PAYG rate at $0.768/hr
# confirmed live), and picking `items[0]` without filtering grabbed
# whichever came back first -- silently undercounting real cost by up
# to 5x on larger VM sizes.
#
# Fixing this isn't as simple as requiring skuName == armSkuName: Azure
# is inconsistent about it -- D-series has skuName "Standard_D16s_v5"
# (matches armSkuName), but B-series has skuName "B1s" (no "Standard_"
# prefix, confirmed live) -- an exact-match filter silently breaks
# B-series lookups. Excluding Spot/Low Priority by substring works for
# both.
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


# Real check: VMs powered off via `az vm stop` (or the portal's "Stop"
# button) rather than `az vm deallocate` -- Azure's own CLI help says it
# plainly: "The VM will continue to be billed. To avoid this, you can
# deallocate the VM." PowerState reports "VM stopped" (still billed) vs
# "VM deallocated" (not billed) -- this checks the real power state, not
# just whether the VM appears "off" in a way that could be conflated with
# the free state.
#
# Real bug fixed: this used to hardcode a flat B1s price ($0.0104/hr)
# for every stopped VM regardless of its actual size -- a large VM's
# waste could be underpriced by 50x or more. Now fetches the live
# price per VM's real size, same approach used in vm_sizing.py.
@registry.register_source("azure.stopped_not_deallocated_vms")
class AzureStoppedNotDeallocatedVmsSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")

    def extract(self, context: Any = None) -> pa.Table:
        cmd = ["az", "vm", "list", "-d", "--query",
               "[?powerState=='VM stopped'].{id:id,name:name,resourceGroup:resourceGroup,vmSize:hardwareProfile.vmSize,powerState:powerState,location:location}"]
        if self.resource_group:
            cmd += ["--resource-group", self.resource_group]

        raw = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        vms = json.loads(raw)

        if not vms:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "resource_group": pa.array([], type=pa.string()),
                "vm_size": pa.array([], type=pa.string()),
                "hourly_price": pa.array([], type=pa.float64()),
            })

        return pa.table({
            "resource_id": [v["id"].lower() for v in vms],
            "resource_name": [v["name"] for v in vms],
            "resource_group": [v["resourceGroup"] for v in vms],
            "vm_size": [v["vmSize"] for v in vms],
            "hourly_price": [
                _fetch_hourly_price(v["vmSize"], _normalize_region(v.get("location", "eastus")))
                for v in vms
            ],
        })
