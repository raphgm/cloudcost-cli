import json
import subprocess
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: storage accounts with zero blob containers -- provisioned,
# billing a small fixed baseline, storing nothing. Uses the CLI's own
# authenticated session (--auth-mode login), matching the auth pattern
# every other source in this project already relies on.
@registry.register_source("azure.empty_storage_accounts")
class AzureEmptyStorageAccountsSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")

    def extract(self, context: Any = None) -> pa.Table:
        cmd = ["az", "storage", "account", "list", "--query",
               "[].{id:id,name:name,resourceGroup:resourceGroup,sku:sku.name,location:location}"]
        if self.resource_group:
            cmd += ["--resource-group", self.resource_group]

        raw = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        accounts = json.loads(raw)

        empty = []
        for acct in accounts:
            containers_raw = subprocess.run(
                ["az", "storage", "container", "list", "--account-name", acct["name"], "--auth-mode", "login", "-o", "json"],
                capture_output=True, text=True,
            ).stdout
            try:
                containers = json.loads(containers_raw) if containers_raw.strip() else []
            except json.JSONDecodeError:
                continue  # couldn't authorize against this account -- skip rather than guess
            if not containers:
                empty.append(acct)

        if not empty:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "resource_group": pa.array([], type=pa.string()),
                "sku": pa.array([], type=pa.string()),
                "location": pa.array([], type=pa.string()),
            })

        return pa.table({
            "resource_id": [a["id"].lower() for a in empty],
            "resource_name": [a["name"] for a in empty],
            "resource_group": [a["resourceGroup"] for a in empty],
            "sku": [a["sku"] for a in empty],
            "location": [a["location"] for a in empty],
        })
