import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: Azure Health Data Services FHIR services bill a fixed
# hourly "Service Runtime" fee whether real API traffic hits the
# service or not. Price is Azure's real, current "Standard Service
# Runtime" meter (Retail Prices API, product "Azure Health Data
# APIs"): $0.40/hour. "TotalRequests" metric confirmed via
# `az monitor metrics list-definitions --resource <fhir-service-id>`.
@registry.register_source("azure.idle_health_data_fhir")
class AzureIdleHealthDataFhirSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.idle_health_data_fhir requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        workspaces_raw = subprocess.run(
            ["az", "healthcareapis", "workspace", "list", "--resource-group", self.resource_group,
             "--query", "[].name", "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        workspaces = json.loads(workspaces_raw)

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        rows = []
        for workspace_name in workspaces:
            services_raw = subprocess.run(
                ["az", "healthcareapis", "workspace", "fhir-service", "list",
                 "--resource-group", self.resource_group, "--workspace-name", workspace_name,
                 "--query", "[].{id:id,name:name}", "-o", "json"],
                capture_output=True, text=True, check=True,
            ).stdout
            services = json.loads(services_raw)

            for service in services:
                raw = subprocess.run(
                    [
                        "az", "monitor", "metrics", "list",
                        "--resource", service["id"],
                        "--metric", "TotalRequests",
                        "--aggregation", "Total",
                        "--interval", "PT1H",
                        "--start-time", start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "--end-time", end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    ],
                    capture_output=True, text=True, check=True,
                ).stdout
                parsed = json.loads(raw)

                total_requests = 0.0
                for timeseries in parsed.get("value", []):
                    for series in timeseries.get("timeseries", []):
                        for point in series.get("data", []):
                            total_requests += point.get("total") or 0.0

                rows.append({
                    "resource_id": service["id"].lower(),
                    "resource_name": service["name"],
                    "workspace_name": workspace_name,
                    "total_requests": total_requests,
                    "lookback_days": self.lookback_days,
                })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "workspace_name": pa.array([], type=pa.string()),
                "total_requests": pa.array([], type=pa.float64()),
                "lookback_days": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "workspace_name": [r["workspace_name"] for r in rows],
            "total_requests": [r["total_requests"] for r in rows],
            "lookback_days": [r["lookback_days"] for r in rows],
        })
