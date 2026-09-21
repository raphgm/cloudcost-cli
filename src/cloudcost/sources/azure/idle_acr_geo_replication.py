import json
import subprocess
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: Premium Container Registries with geo-replicas bill the
# full Premium tier rate for EACH replica region, not just the primary --
# distinct from idle_container_registries.py, which only flags a whole
# registry with zero repositories. A registry with N replicas is paying
# for N x Premium regardless of whether anything actually pulls images
# from those replica regions. Governance-style check (real inventory via
# `az acr replication list`, no per-region pull metric needed -- ACR
# doesn't expose per-replica pull counts via Azure Monitor).
@registry.register_source("azure.idle_acr_geo_replication")
class AzureIdleAcrGeoReplicationSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        if not self.resource_group:
            raise ValueError("azure.idle_acr_geo_replication requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        registries_raw = subprocess.run(
            ["az", "acr", "list", "--resource-group", self.resource_group,
             "--query", "[?sku.tier=='Premium'].{id:id,name:name,location:location}", "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        registries = json.loads(registries_raw)

        rows = []
        for reg in registries:
            replicas_raw = subprocess.run(
                ["az", "acr", "replication", "list", "--registry", reg["name"],
                 "--query", "[].location", "-o", "json"],
                capture_output=True, text=True, check=True,
            ).stdout
            replica_locations = json.loads(replicas_raw)

            extra_replicas = [
                loc for loc in replica_locations
                if loc.replace(" ", "").lower() != reg["location"].replace(" ", "").lower()
            ]

            if not extra_replicas:
                continue

            rows.append({
                "resource_id": reg["id"].lower(),
                "resource_name": reg["name"],
                "primary_location": reg["location"],
                "extra_replica_count": len(extra_replicas),
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "primary_location": pa.array([], type=pa.string()),
                "extra_replica_count": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "primary_location": [r["primary_location"] for r in rows],
            "extra_replica_count": [r["extra_replica_count"] for r in rows],
        })
