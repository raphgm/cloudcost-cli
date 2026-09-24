# Explicit allow-list of policies that can be auto-remediated, and how.
#
# This is intentionally conservative and small: only checks where the
# remediation is either fully reversible (deallocate, not delete) or
# operates on a resource that is unambiguously unused by definition of
# the check itself (unattached disk, unassociated IP, an orphaned
# snapshot older than 30 days). Every other finding -- even ones that
# look "obviously idle" -- is refused by default rather than guessed
# at, because a false positive on delete is unrecoverable.
#
# Adding a policy here is a deliberate, reviewed decision, not a
# generic "delete whatever a check flags" mechanism.

from dataclasses import dataclass


@dataclass(frozen=True)
class RemediationAction:
    action: str  # human label: "deallocate" | "delete"
    risk: str  # "low" (reversible) | "medium" (destructive, but scoped)
    command: list[str]  # az CLI argv template; "{id}" is replaced with the resource id
    description: str


REMEDIATION_REGISTRY: dict[str, RemediationAction] = {
    "stopped_not_deallocated_vms": RemediationAction(
        action="deallocate",
        risk="low",
        command=["az", "vm", "deallocate", "--ids", "{id}"],
        description="Deallocate the VM (stops compute billing; disk/network charges remain; fully reversible via `az vm start`).",
    ),
    "unattached_disks": RemediationAction(
        action="delete",
        risk="medium",
        command=["az", "disk", "delete", "--ids", "{id}", "--yes"],
        description="Delete the managed disk (not attached to any VM by definition of this check).",
    ),
    "unassociated_public_ips": RemediationAction(
        action="delete",
        risk="medium",
        command=["az", "network", "public-ip", "delete", "--ids", "{id}"],
        description="Delete the public IP address (not associated with any resource by definition of this check).",
    ),
    "old_snapshots": RemediationAction(
        action="delete",
        risk="medium",
        command=["az", "snapshot", "delete", "--ids", "{id}", "--yes"],
        description="Delete the disk snapshot (older than the check's retention threshold).",
    ),
}


def get_action(policy_name: str) -> RemediationAction | None:
    return REMEDIATION_REGISTRY.get(policy_name)
