import json
import subprocess
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: Load Balancers where every backend pool is empty — reserved,
# billing, routing traffic to nothing. A Load Balancer is only flagged if
# it has at least one backend pool AND none of them have any members;
# a brand-new LB mid-setup with zero pools at all isn't the same finding.
#
# Real quirk found building this: `backendIPConfigurations` on an empty
# pool comes back as JSON null, not an empty array — a naive
# `length(backendIPConfigurations)` JMESPath query errors on that, so this
# checks for null-or-empty explicitly rather than assuming array shape.
@registry.register_source("azure.idle_load_balancers")
class AzureIdleLoadBalancersSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")

    def extract(self, context: Any = None) -> pa.Table:
        cmd = ["az", "network", "lb", "list", "--query",
               "[].{id:id,name:name,resourceGroup:resourceGroup,sku:sku.name,location:location,backendAddressPools:backendAddressPools}"]
        if self.resource_group:
            cmd += ["--resource-group", self.resource_group]

        raw = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        lbs = json.loads(raw)

        idle = []
        for lb in lbs:
            pools = lb.get("backendAddressPools") or []
            if not pools:
                continue
            all_empty = all(not (p.get("backendIPConfigurations") or []) for p in pools)
            if all_empty:
                idle.append(lb)

        if not idle:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "resource_group": pa.array([], type=pa.string()),
                "sku": pa.array([], type=pa.string()),
                "location": pa.array([], type=pa.string()),
            })

        return pa.table({
            "resource_id": [lb["id"].lower() for lb in idle],
            "resource_name": [lb["name"] for lb in idle],
            "resource_group": [lb["resourceGroup"] for lb in idle],
            "sku": [lb["sku"] for lb in idle],
            "location": [lb["location"] for lb in idle],
        })
