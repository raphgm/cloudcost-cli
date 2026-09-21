import json
import subprocess
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: every Azure DNS zone always carries exactly 2 default
# record sets (SOA + NS) even when empty -- confirmed by creating a real
# zone and checking `numberOfRecordSets`. A zone with no more than that
# has no real A/CNAME/MX/etc records, meaning nothing actually resolves
# through it, yet it still bills the flat $0.50/month zone-hosting fee
# (Retail Prices API, 'Azure DNS' service, 'Public Zone' meter).
# This is a governance-style check (like empty_storage_accounts.py) --
# no usage metric needed, the record count itself is the evidence.
@registry.register_source("azure.idle_dns_zone")
class AzureIdleDnsZoneSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        if not self.resource_group:
            raise ValueError("azure.idle_dns_zone requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        zones_raw = subprocess.run(
            ["az", "network", "dns", "zone", "list", "--resource-group", self.resource_group,
             "--query", "[].{id:id,name:name,recordSets:numberOfRecordSets}", "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        zones = json.loads(zones_raw)

        if not zones:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "record_set_count": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [z["id"].lower() for z in zones],
            "resource_name": [z["name"] for z in zones],
            "record_set_count": [z.get("recordSets", 2) for z in zones],
        })
