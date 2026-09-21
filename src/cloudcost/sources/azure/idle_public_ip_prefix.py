import json
import subprocess
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: a Public IP Prefix reserves a whole block of addresses
# (2^(32-prefixLength) for IPv4) at creation time -- distinct resource
# type from a single Public IP Address, and distinct waste from
# unassociated_public_ips.py, which only checks individual IPs. Each
# address in the block bills at the standard Public IP rate
# ($3.65/month, same real price used in unassociated_public_ips.sql)
# whether a real Public IP resource has actually been carved out of it
# or not. Governance-style check (real inventory via
# `az network public-ip prefix list` + `az network public-ip list`, no
# metric needed): a prefix with zero real IPs allocated from it is
# pure reserved-capacity waste across the whole block.
@registry.register_source("azure.idle_public_ip_prefix")
class AzureIdlePublicIpPrefixSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        if not self.resource_group:
            raise ValueError("azure.idle_public_ip_prefix requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        prefixes_raw = subprocess.run(
            ["az", "network", "public-ip", "prefix", "list", "--resource-group", self.resource_group,
             "--query", "[].{id:id,name:name,prefixLength:prefixLength}", "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        prefixes = json.loads(prefixes_raw)

        ips_raw = subprocess.run(
            ["az", "network", "public-ip", "list", "--resource-group", self.resource_group,
             "--query", "[].publicIPPrefix.id", "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        ip_prefix_refs = [ref for ref in json.loads(ips_raw) if ref]

        rows = []
        for prefix in prefixes:
            reserved_addresses = 2 ** (32 - prefix["prefixLength"])
            allocated_count = sum(1 for ref in ip_prefix_refs if ref.lower() == prefix["id"].lower())

            rows.append({
                "resource_id": prefix["id"].lower(),
                "resource_name": prefix["name"],
                "reserved_addresses": reserved_addresses,
                "allocated_count": allocated_count,
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "reserved_addresses": pa.array([], type=pa.int64()),
                "allocated_count": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "reserved_addresses": [r["reserved_addresses"] for r in rows],
            "allocated_count": [r["allocated_count"] for r in rows],
        })
