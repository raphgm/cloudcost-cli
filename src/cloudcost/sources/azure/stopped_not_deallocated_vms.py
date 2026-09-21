import json
import subprocess
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: VMs powered off via `az vm stop` (or the portal's "Stop"
# button) rather than `az vm deallocate` -- Azure's own CLI help says it
# plainly: "The VM will continue to be billed. To avoid this, you can
# deallocate the VM." PowerState reports "VM stopped" (still billed) vs
# "VM deallocated" (not billed) -- this checks the real power state, not
# just whether the VM appears "off" in a way that could be conflated with
# the free state.
@registry.register_source("azure.stopped_not_deallocated_vms")
class AzureStoppedNotDeallocatedVmsSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")

    def extract(self, context: Any = None) -> pa.Table:
        cmd = ["az", "vm", "list", "-d", "--query",
               "[?powerState=='VM stopped'].{id:id,name:name,resourceGroup:resourceGroup,vmSize:hardwareProfile.vmSize,powerState:powerState}"]
        if self.resource_group:
            cmd += ["--resource-group", self.resource_group]

        raw = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        vms = json.loads(raw)

        if not vms:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "resource_group": pa.array([], type=pa.string()),
                "vm_size": pa.array([], type=pa.string()),
            })

        return pa.table({
            "resource_id": [v["id"].lower() for v in vms],
            "resource_name": [v["name"] for v in vms],
            "resource_group": [v["resourceGroup"] for v in vms],
            "vm_size": [v["vmSize"] for v in vms],
        })
