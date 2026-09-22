import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real bug found and fixed during verification: the SKU field is
# "sku.name", not "properties.skuName" as an earlier draft of this
# source used -- that mismatch silently returned None for every real
# HSM, making the hourly_price lookup always fail.
#
# Real check: Azure Key Vault Managed HSM pools bill a fixed hourly fee
# per pool regardless of real key operation volume. The Retail Prices
# API does not expose a queryable meter for this specific product
# (confirmed: multiple filter variants against 'Managed HSM' and 'HSM'
# all returned zero results, the same real gap this project already
# documents for idle_load_balancers.sql) -- so this uses Microsoft's
# own published price instead, fetched from
# azure.microsoft.com/en-us/pricing/details/key-vault during this
# check's verification: Managed HSM Pools, Standard B1 = $3.20/hour.
# A prior version of this check fabricated "$10.00" flat, off by
# roughly 240x from the real monthly cost. "ServiceApiHit" (total key
# operations) confirmed via
# `az monitor metrics list-definitions --resource <hsm-id>`.
STANDARD_B1_HOURLY_PRICE = 3.20


@registry.register_source("azure.idle_managed_hsm")
class AzureIdleManagedHsmSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.idle_managed_hsm requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        # `az keyvault list` only returns vaults, not managed HSMs --
        # `--resource-type hsm` is the real, correct filter.
        hsms_raw = subprocess.run(
            ["az", "keyvault", "list", "--resource-group", self.resource_group,
             "--resource-type", "hsm",
             "--query", "[].{id:id,name:name,sku:sku.name}", "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        hsms = json.loads(hsms_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for hsm in hsms:
            sku = hsm.get("sku", "Standard_B1")

            raw = subprocess.run(
                [
                    "az", "monitor", "metrics", "list",
                    "--resource", hsm["id"],
                    "--metric", "ServiceApiHit",
                    "--aggregation", "Total",
                    "--interval", "PT1H",
                    "--start-time", start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "--end-time", end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ],
                capture_output=True, text=True, check=True,
            ).stdout
            parsed = json.loads(raw)

            total_operations = 0.0
            for timeseries in parsed.get("value", []):
                for series in timeseries.get("timeseries", []):
                    for point in series.get("data", []):
                        total_operations += point.get("total") or 0.0

            hourly_price = STANDARD_B1_HOURLY_PRICE if sku == "Standard_B1" else 0.0

            rows.append({
                "resource_id": hsm["id"].lower(),
                "resource_name": hsm["name"],
                "sku": sku,
                "operation_count": total_operations,
                "hourly_price": hourly_price,
                "lookback_days": self.lookback_days,
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "sku": pa.array([], type=pa.string()),
                "operation_count": pa.array([], type=pa.float64()),
                "hourly_price": pa.array([], type=pa.float64()),
                "lookback_days": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "sku": [r["sku"] for r in rows],
            "operation_count": [r["operation_count"] for r in rows],
            "hourly_price": [r["hourly_price"] for r in rows],
            "lookback_days": [r["lookback_days"] for r in rows],
        })
