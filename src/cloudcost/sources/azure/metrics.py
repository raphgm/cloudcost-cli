import json
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry

# Real Azure Monitor metric names, confirmed against a live VM via
# `az monitor metrics list-definitions`. CPU alone tells you a VM is idle;
# it doesn't tell you whether it's quietly serving real network or disk
# traffic that CPU utilization wouldn't reflect (e.g. a lightly-loaded
# file server). Checking all four before calling something a rightsizing
# candidate is the real difference between a confident finding and a
# false positive.
METRIC_NAMES = [
    "Percentage CPU",
    "Network In Total",
    "Network Out Total",
    "Disk Read Operations/Sec",
    "Disk Write Operations/Sec",
]

METRIC_COLUMN_MAP = {
    "Percentage CPU": "avg_cpu_percent",
    "Network In Total": "avg_network_in_bytes",
    "Network Out Total": "avg_network_out_bytes",
    "Disk Read Operations/Sec": "avg_disk_read_ops",
    "Disk Write Operations/Sec": "avg_disk_write_ops",
}


# Real Azure Monitor multi-metric utilization, via the Azure CLI's own
# authenticated session (az monitor metrics list) — the same auth pattern
# as azure.cost_export. This is what allows a rightsizing policy to be a
# genuine measurement instead of the "we simulate a finding" placeholder
# zero_utilization.sql shipped with before this: cost data alone can tell
# you a VM is expensive, never whether it's actually being used.
@registry.register_source("azure.vm_metrics")
class AzureVmMetricsSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        # 7 days by default: a single day can catch a VM mid-anomaly
        # (a one-off batch job, a reboot) and either over- or
        # under-report its normal utilization. A week smooths that out.
        self.lookback_days = config.get("lookback_days", 7)
        if not self.resource_group:
            raise ValueError("azure.vm_metrics requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        vm_ids_raw = subprocess.run(
            ["az", "vm", "list", "--resource-group", self.resource_group, "--query", "[].id", "-o", "tsv"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        vm_ids = [v for v in vm_ids_raw.splitlines() if v]

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=self.lookback_days)

        # keyed by (resource_id, timestamp) -> {column_name: value}
        by_key: dict = defaultdict(dict)

        for vm_id in vm_ids:
            raw = subprocess.run(
                [
                    "az", "monitor", "metrics", "list",
                    "--resource", vm_id,
                    "--metric", ",".join(METRIC_NAMES),
                    "--aggregation", "Average",
                    "--interval", "PT1H",
                    "--start-time", start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "--end-time", end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                ],
                capture_output=True, text=True, check=True,
            ).stdout
            parsed = json.loads(raw)

            for timeseries in parsed.get("value", []):
                metric_name = timeseries.get("name", {}).get("value")
                column = METRIC_COLUMN_MAP.get(metric_name)
                if column is None:
                    continue
                for series in timeseries.get("timeseries", []):
                    for point in series.get("data", []):
                        avg_value = point.get("average")
                        if avg_value is None:
                            continue
                        key = (vm_id.lower(), point["timeStamp"])
                        by_key[key]["resource_id"] = vm_id.lower()
                        by_key[key]["resource_name"] = vm_id.split("/")[-1]
                        by_key[key]["timestamp"] = point["timeStamp"]
                        by_key[key][column] = float(avg_value)

        columns = ["resource_id", "resource_name", "timestamp"] + list(METRIC_COLUMN_MAP.values())
        if not by_key:
            return pa.table({c: pa.array([], type=pa.string() if c in ("resource_id", "resource_name", "timestamp") else pa.float64()) for c in columns})

        rows = list(by_key.values())
        return pa.table({
            c: [r.get(c) for r in rows]
            for c in columns
        })
