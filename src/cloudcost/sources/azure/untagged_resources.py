import json
import subprocess
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real governance check: resources with no tags at all. Deliberately
# detection-only — this project does not stop or delete anything.
# Honest limitation: Azure Resource Manager doesn't expose a creation
# timestamp uniformly across all resource types (some do via
# `properties.timeCreated`, most don't), so this reports what's real and
# checkable (untagged right now) rather than fabricating an "age" figure
# that would need per-resource-type handling this doesn't implement yet.
@registry.register_source("azure.untagged_resources")
class AzureUntaggedResourcesSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")

    def extract(self, context: Any = None) -> pa.Table:
        cmd = [
            "az", "resource", "list", "--query",
            "[?tags==null || length(keys(tags))==`0`].{id:id,name:name,type:type,resourceGroup:resourceGroup,location:location}",
        ]
        if self.resource_group:
            cmd += ["--resource-group", self.resource_group]

        raw = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        resources = json.loads(raw)

        if not resources:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "resource_type": pa.array([], type=pa.string()),
                "resource_group": pa.array([], type=pa.string()),
                "location": pa.array([], type=pa.string()),
            })

        return pa.table({
            "resource_id": [r["id"].lower() for r in resources],
            "resource_name": [r["name"] for r in resources],
            "resource_type": [r["type"] for r in resources],
            "resource_group": [r["resourceGroup"] for r in resources],
            "location": [r["location"] for r in resources],
        })
