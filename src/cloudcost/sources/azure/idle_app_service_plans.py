import json
import subprocess
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: App Service Plans with zero deployed web apps -- reserved
# compute, billing every month, hosting nothing. Real CLI quirk found
# building this: `az appservice plan show --query "numberOfSites"`
# returns empty even though the field is genuinely populated in the full
# object; `az appservice plan list` includes it correctly. Uses list for
# that reason, not because it's the more obvious choice.
@registry.register_source("azure.idle_app_service_plans")
class AzureIdleAppServicePlansSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")

    def extract(self, context: Any = None) -> pa.Table:
        cmd = ["az", "appservice", "plan", "list", "-o", "json"]
        if self.resource_group:
            cmd += ["--resource-group", self.resource_group]

        raw = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        plans = json.loads(raw)

        idle = [p for p in plans if p.get("numberOfSites", 0) == 0]

        if not idle:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "resource_group": pa.array([], type=pa.string()),
                "sku": pa.array([], type=pa.string()),
                "location": pa.array([], type=pa.string()),
            })

        return pa.table({
            "resource_id": [p["id"].lower() for p in idle],
            "resource_name": [p["name"] for p in idle],
            "resource_group": [p["resourceGroup"] for p in idle],
            "sku": [p["sku"]["name"] for p in idle],
            "location": [p["location"] for p in idle],
        })
