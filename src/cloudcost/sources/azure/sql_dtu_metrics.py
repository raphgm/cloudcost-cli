import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real DTU utilization for DTU-based Azure SQL databases (Basic/Standard/
# Premium tiers) via Azure Monitor's real dtu_consumption_percent metric.
# vCore-based databases expose cpu_percent instead — not handled by this
# check yet, a real, honest limitation, not silently wrong output.
@registry.register_source("azure.sql_dtu_metrics")
class AzureSqlDtuMetricsSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.sql_dtu_metrics requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        servers_raw = subprocess.run(
            ["az", "sql", "server", "list", "--resource-group", self.resource_group, "--query", "[].name", "-o", "tsv"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        servers = [s for s in servers_raw.splitlines() if s]

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for server in servers:
            dbs_raw = subprocess.run(
                ["az", "sql", "db", "list", "--resource-group", self.resource_group, "--server", server,
                 "--query", "[?name!='master'].{id:id,name:name,edition:edition}", "-o", "json"],
                capture_output=True, text=True, check=True,
            ).stdout
            for db in json.loads(dbs_raw):
                if db.get("edition") not in ("Basic", "Standard", "Premium"):
                    continue  # vCore-based, needs cpu_percent instead -- not this check

                raw = subprocess.run(
                    [
                        "az", "monitor", "metrics", "list",
                        "--resource", db["id"],
                        "--metric", "dtu_consumption_percent",
                        "--aggregation", "Average",
                        "--interval", "PT1H",
                        "--start-time", start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "--end-time", end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    ],
                    capture_output=True, text=True, check=True,
                ).stdout
                parsed = json.loads(raw)

                for timeseries in parsed.get("value", []):
                    for series in timeseries.get("timeseries", []):
                        for point in series.get("data", []):
                            avg_dtu = point.get("average")
                            if avg_dtu is None:
                                continue
                            rows.append({
                                "resource_id": db["id"].lower(),
                                "resource_name": db["name"],
                                "timestamp": point["timeStamp"],
                                "avg_dtu_percent": float(avg_dtu),
                            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "timestamp": pa.array([], type=pa.string()),
                "avg_dtu_percent": pa.array([], type=pa.float64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "timestamp": [r["timestamp"] for r in rows],
            "avg_dtu_percent": [r["avg_dtu_percent"] for r in rows],
        })
