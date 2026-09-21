import json
import subprocess
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: Premium SSD v2 / Ultra disks provision IOPS and throughput
# as separate billed dimensions from capacity, and bill continuously
# above the included free baseline (3000 IOPS / 125 MBps) whether the
# disk is attached to anything or not. This is a governance-style check
# (real inventory, no metric needed) distinct from unattached_disks.py,
# which only checks capacity -- an unattached disk here still bills its
# real IOPS/throughput overage.
FREE_BASELINE_IOPS = 3000
FREE_BASELINE_MBPS = 125


@registry.register_source("azure.idle_premiumv2_disk_overage")
class AzureIdlePremiumV2DiskOverageSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        if not self.resource_group:
            raise ValueError("azure.idle_premiumv2_disk_overage requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        disks_raw = subprocess.run(
            ["az", "disk", "list", "--resource-group", self.resource_group,
             "--query", "[?sku.name=='PremiumV2_LRS' || sku.name=='UltraSSD_LRS'].{id:id,name:name,sku:sku.name,diskIOPSReadWrite:diskIOPSReadWrite,diskMBpsReadWrite:diskMBpsReadWrite,diskState:diskState}",
             "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        disks = json.loads(disks_raw)

        rows = []
        for disk in disks:
            if disk.get("diskState") != "Unattached":
                continue

            iops = disk.get("diskIOPSReadWrite", 0) or 0
            mbps = disk.get("diskMBpsReadWrite", 0) or 0
            overage_iops = max(0, iops - FREE_BASELINE_IOPS)
            overage_mbps = max(0, mbps - FREE_BASELINE_MBPS)

            if overage_iops == 0 and overage_mbps == 0:
                continue

            rows.append({
                "resource_id": disk["id"].lower(),
                "resource_name": disk["name"],
                "sku": disk.get("sku", "PremiumV2_LRS"),
                "overage_iops": overage_iops,
                "overage_mbps": overage_mbps,
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "sku": pa.array([], type=pa.string()),
                "overage_iops": pa.array([], type=pa.int64()),
                "overage_mbps": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "sku": [r["sku"] for r in rows],
            "overage_iops": [r["overage_iops"] for r in rows],
            "overage_mbps": [r["overage_mbps"] for r in rows],
        })
