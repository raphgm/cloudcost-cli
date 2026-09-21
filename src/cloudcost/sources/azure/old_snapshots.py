import json
import subprocess
from datetime import datetime, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: disk snapshots and their real age, computed from Azure's
# own timeCreated timestamp — not estimated. Snapshots are a real, common
# cost-creep pattern: taken once for a migration or a "just in case"
# backup, then never reviewed again while billing every month.
@registry.register_source("azure.old_snapshots")
class AzureOldSnapshotsSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")

    def extract(self, context: Any = None) -> pa.Table:
        cmd = ["az", "snapshot", "list", "--query",
               "[].{id:id,name:name,resourceGroup:resourceGroup,diskSizeGb:diskSizeGB,sku:sku.name,timeCreated:timeCreated,location:location}"]
        if self.resource_group:
            cmd += ["--resource-group", self.resource_group]

        raw = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        snapshots = json.loads(raw)

        if not snapshots:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "resource_group": pa.array([], type=pa.string()),
                "size_gb": pa.array([], type=pa.int64()),
                "sku": pa.array([], type=pa.string()),
                "age_days": pa.array([], type=pa.int64()),
                "location": pa.array([], type=pa.string()),
            })

        now = datetime.now(timezone.utc)
        ages = []
        for s in snapshots:
            created = datetime.fromisoformat(s["timeCreated"].replace("Z", "+00:00"))
            ages.append((now - created).days)

        return pa.table({
            "resource_id": [s["id"].lower() for s in snapshots],
            "resource_name": [s["name"] for s in snapshots],
            "resource_group": [s["resourceGroup"] for s in snapshots],
            "size_gb": [s["diskSizeGb"] for s in snapshots],
            "sku": [s["sku"] for s in snapshots],
            "age_days": ages,
            "location": [s["location"] for s in snapshots],
        })
