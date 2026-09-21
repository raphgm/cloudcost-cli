import json
import subprocess
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: NAT Gateways with no subnet attached -- reserved, billing
# an hourly rate for a resource routing traffic for nothing. Real quirk
# found: subnets comes back as JSON null when unattached, same pattern
# as azure.idle_load_balancers' backendIPConfigurations.
@registry.register_source("azure.idle_nat_gateways")
class AzureIdleNatGatewaysSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")

    def extract(self, context: Any = None) -> pa.Table:
        cmd = ["az", "network", "nat", "gateway", "list", "--query",
               "[].{id:id,name:name,resourceGroup:resourceGroup,sku:sku.name,location:location,subnets:subnets}"]
        if self.resource_group:
            cmd += ["--resource-group", self.resource_group]

        raw = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        gateways = json.loads(raw)

        idle = [g for g in gateways if not g.get("subnets")]

        if not idle:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "resource_group": pa.array([], type=pa.string()),
                "sku": pa.array([], type=pa.string()),
                "location": pa.array([], type=pa.string()),
            })

        return pa.table({
            "resource_id": [g["id"].lower() for g in idle],
            "resource_name": [g["name"] for g in idle],
            "resource_group": [g["resourceGroup"] for g in idle],
            "sku": [g["sku"] for g in idle],
            "location": [g["location"] for g in idle],
        })
