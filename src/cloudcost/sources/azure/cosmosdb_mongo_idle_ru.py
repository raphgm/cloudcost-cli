import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: Cosmos DB for MongoDB API databases with fixed
# (non-autoscale) provisioned throughput reserve RU/s and bill for it
# whether consumed or not -- same waste pattern as
# azure.cosmosdb_idle_ru, but that check only covers the SQL API
# (`az cosmosdb sql database ...`); MongoDB API databases use a
# genuinely different CLI surface (`az cosmosdb mongodb database ...`)
# even though the underlying RU billing is identical.
@registry.register_source("azure.cosmosdb_mongo_idle_ru")
class AzureCosmosDbMongoIdleRuSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.cosmosdb_mongo_idle_ru requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        accounts_raw = subprocess.run(
            ["az", "cosmosdb", "list", "--resource-group", self.resource_group,
             "--query", "[?kind=='MongoDB'].{id:id,name:name,capabilities:capabilities}", "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        accounts = json.loads(accounts_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for acct in accounts:
            capability_names = [c.get("name") for c in (acct.get("capabilities") or [])]
            if "EnableServerless" in capability_names:
                continue

            db_names_raw = subprocess.run(
                ["az", "cosmosdb", "mongodb", "database", "list", "--account-name", acct["name"],
                 "--resource-group", self.resource_group, "--query", "[].name", "-o", "json"],
                capture_output=True, text=True, check=True,
            ).stdout
            db_names = json.loads(db_names_raw)

            provisioned_ru = 0
            for db_name in db_names:
                try:
                    throughput_raw = subprocess.run(
                        ["az", "cosmosdb", "mongodb", "database", "throughput", "show",
                         "--account-name", acct["name"], "--resource-group", self.resource_group,
                         "--name", db_name, "--query", "resource.throughput", "-o", "tsv"],
                        capture_output=True, text=True, check=True,
                    ).stdout.strip()
                    if throughput_raw and throughput_raw != "None":
                        provisioned_ru += int(throughput_raw)
                except subprocess.CalledProcessError:
                    continue

            raw = subprocess.run(
                [
                    "az", "monitor", "metrics", "list",
                    "--resource", acct["id"],
                    "--metric", "TotalRequestUnits",
                    "--aggregation", "Total",
                    "--interval", "PT1H",
                    "--start-time", start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "--end-time", end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ],
                capture_output=True, text=True, check=True,
            ).stdout
            parsed = json.loads(raw)

            total_ru_consumed = 0.0
            for timeseries in parsed.get("value", []):
                for series in timeseries.get("timeseries", []):
                    for point in series.get("data", []):
                        total_ru_consumed += point.get("total") or 0.0

            rows.append({
                "resource_id": acct["id"].lower(),
                "resource_name": acct["name"],
                "provisioned_ru": provisioned_ru,
                "total_ru_consumed": total_ru_consumed,
                "lookback_days": self.lookback_days,
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "provisioned_ru": pa.array([], type=pa.int64()),
                "total_ru_consumed": pa.array([], type=pa.float64()),
                "lookback_days": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "provisioned_ru": [r["provisioned_ru"] for r in rows],
            "total_ru_consumed": [r["total_ru_consumed"] for r in rows],
            "lookback_days": [r["lookback_days"] for r in rows],
        })
