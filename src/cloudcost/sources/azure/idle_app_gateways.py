import json
import subprocess
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: Application Gateways where every backend pool has no
# addresses/targets -- reserved, billing hourly plus a capacity-unit
# rate, routing traffic to nothing. Same idle-backend-pool pattern as
# azure.idle_load_balancers, applied to App Gateway's own backend pool
# shape (backendAddresses / backendIPConfigurations, not just one field).
@registry.register_source("azure.idle_app_gateways")
class AzureIdleAppGatewaysSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")

    def extract(self, context: Any = None) -> pa.Table:
        cmd = ["az", "network", "application-gateway", "list", "--query",
               "[].{id:id,name:name,resourceGroup:resourceGroup,sku:sku.name,location:location,backendAddressPools:backendAddressPools}"]
        if self.resource_group:
            cmd += ["--resource-group", self.resource_group]

        raw = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        gateways = json.loads(raw)

        idle = []
        for gw in gateways:
            pools = gw.get("backendAddressPools") or []
            if not pools:
                continue
            all_empty = all(
                not (p.get("backendAddresses") or []) and not (p.get("backendIPConfigurations") or [])
                for p in pools
            )
            if all_empty:
                idle.append(gw)

        if not idle:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "resource_group": pa.array([], type=pa.string()),
                "sku": pa.array([], type=pa.string()),
                "location": pa.array([], type=pa.string()),
            })

        return pa.table({
            "resource_id": [gw["id"].lower() for gw in idle],
            "resource_name": [gw["name"] for gw in idle],
            "resource_group": [gw["resourceGroup"] for gw in idle],
            "sku": [gw["sku"] for gw in idle],
            "location": [gw["location"] for gw in idle],
        })
