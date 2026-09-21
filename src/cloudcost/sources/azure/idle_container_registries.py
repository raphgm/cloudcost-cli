import json
import subprocess
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: Standard/Premium Container Registries with zero repositories
# -- reserved, billing a fixed daily rate, storing no images. Basic tier
# is cheap enough ($0.167/day) that it's not worth flagging here; Standard
# and Premium are the tiers where an empty registry is a real waste.
@registry.register_source("azure.idle_container_registries")
class AzureIdleContainerRegistriesSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")

    def extract(self, context: Any = None) -> pa.Table:
        cmd = ["az", "acr", "list", "--query",
               "[?sku.name=='Standard' || sku.name=='Premium'].{id:id,name:name,resourceGroup:resourceGroup,sku:sku.name,location:location}"]
        if self.resource_group:
            cmd += ["--resource-group", self.resource_group]

        raw = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        registries = json.loads(raw)

        idle = []
        for reg in registries:
            repos_raw = subprocess.run(
                ["az", "acr", "repository", "list", "--name", reg["name"], "-o", "json"],
                capture_output=True, text=True,
            ).stdout
            try:
                repos = json.loads(repos_raw) if repos_raw.strip() else []
            except json.JSONDecodeError:
                continue
            if not repos:
                idle.append(reg)

        if not idle:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "resource_group": pa.array([], type=pa.string()),
                "sku": pa.array([], type=pa.string()),
                "location": pa.array([], type=pa.string()),
            })

        return pa.table({
            "resource_id": [r["id"].lower() for r in idle],
            "resource_name": [r["name"] for r in idle],
            "resource_group": [r["resourceGroup"] for r in idle],
            "sku": [r["sku"] for r in idle],
            "location": [r["location"] for r in idle],
        })
