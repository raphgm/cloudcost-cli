import json
import subprocess
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: Standard SKU public IPs with no ipConfiguration — reserved
# and billing, attached to nothing. A common leftover after a VM, Load
# Balancer, or NAT Gateway is deleted but its IP wasn't released.
@registry.register_source("azure.unassociated_public_ips")
class AzureUnassociatedPublicIpsSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")

    def extract(self, context: Any = None) -> pa.Table:
        cmd = ["az", "network", "public-ip", "list", "--query",
               "[?ipConfiguration==null].{id:id,name:name,resourceGroup:resourceGroup,sku:sku.name,allocationMethod:publicIPAllocationMethod,location:location}"]
        if self.resource_group:
            cmd += ["--resource-group", self.resource_group]

        raw = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        ips = json.loads(raw)

        if not ips:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "resource_group": pa.array([], type=pa.string()),
                "sku": pa.array([], type=pa.string()),
                "allocation_method": pa.array([], type=pa.string()),
                "location": pa.array([], type=pa.string()),
            })

        return pa.table({
            "resource_id": [i["id"].lower() for i in ips],
            "resource_name": [i["name"] for i in ips],
            "resource_group": [i["resourceGroup"] for i in ips],
            "sku": [i["sku"] for i in ips],
            "allocation_method": [i["allocationMethod"] for i in ips],
            "location": [i["location"] for i in ips],
        })
