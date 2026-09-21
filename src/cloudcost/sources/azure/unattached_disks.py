import json
import subprocess
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: managed disks with diskState == "Unattached" — a genuinely
# common, genuinely wasteful pattern (a VM was deleted or resized and its
# disk was left behind, still billing). Uses `az disk list`, the same
# CLI-session auth pattern as every other source in this project.
@registry.register_source("azure.unattached_disks")
class AzureUnattachedDisksSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")

    def extract(self, context: Any = None) -> pa.Table:
        cmd = ["az", "disk", "list", "--query",
               "[?diskState=='Unattached'].{id:id,name:name,resourceGroup:resourceGroup,sizeGb:diskSizeGB,sku:sku.name,location:location}"]
        if self.resource_group:
            cmd += ["--resource-group", self.resource_group]

        raw = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        disks = json.loads(raw)

        if not disks:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "resource_group": pa.array([], type=pa.string()),
                "size_gb": pa.array([], type=pa.int64()),
                "sku": pa.array([], type=pa.string()),
                "location": pa.array([], type=pa.string()),
            })

        return pa.table({
            "resource_id": [d["id"].lower() for d in disks],
            "resource_name": [d["name"] for d in disks],
            "resource_group": [d["resourceGroup"] for d in disks],
            "size_gb": [d["sizeGb"] for d in disks],
            "sku": [d["sku"] for d in disks],
            "location": [d["location"] for d in disks],
        })
