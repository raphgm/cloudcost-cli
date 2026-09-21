import json
import subprocess
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: Network Security Groups attached to nothing -- neither a
# subnet nor a network interface. NSGs are free in Azure (no direct
# billing), so this is a governance/cleanup finding, not a cost-savings
# one -- same honest framing as azure.empty_storage_accounts.
@registry.register_source("azure.orphaned_nsgs")
class AzureOrphanedNsgsSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")

    def extract(self, context: Any = None) -> pa.Table:
        cmd = ["az", "network", "nsg", "list", "--query",
               "[].{id:id,name:name,resourceGroup:resourceGroup,location:location,subnets:subnets,networkInterfaces:networkInterfaces}"]
        if self.resource_group:
            cmd += ["--resource-group", self.resource_group]

        raw = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        nsgs = json.loads(raw)

        orphaned = [n for n in nsgs if not n.get("subnets") and not n.get("networkInterfaces")]

        if not orphaned:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "resource_group": pa.array([], type=pa.string()),
                "location": pa.array([], type=pa.string()),
            })

        return pa.table({
            "resource_id": [n["id"].lower() for n in orphaned],
            "resource_name": [n["name"] for n in orphaned],
            "resource_group": [n["resourceGroup"] for n in orphaned],
            "location": [n["location"] for n in orphaned],
        })
