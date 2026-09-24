import json
from unittest.mock import patch

from cloudcost.remediation.executor import plan, apply_one
from cloudcost.remediation.registry import get_action, REMEDIATION_REGISTRY


def _finding(policy_name, resource_id="/subscriptions/x/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1"):
    return {
        "finding_id": "f-1",
        "policy_name": policy_name,
        "resource_id": resource_id,
        "severity": "medium",
    }


def test_allow_list_only_has_conservative_actions():
    # Every action in the registry must be either a non-destructive
    # "deallocate" (low risk) or a scoped "delete" that only ever
    # targets resources the check itself proved are unused/unattached.
    for name, action in REMEDIATION_REGISTRY.items():
        assert action.action in ("deallocate", "delete")
        assert action.risk in ("low", "medium")
        assert "{id}" in action.command


def test_plan_marks_unknown_policy_unsupported():
    entries = plan([_finding("some_check_not_on_allowlist")])
    assert len(entries) == 1
    assert entries[0]["supported"] is False
    assert "allow-list" in entries[0]["reason"]


def test_plan_marks_known_policy_supported_with_real_command():
    entries = plan([_finding("stopped_not_deallocated_vms")])
    assert entries[0]["supported"] is True
    assert entries[0]["action"] == "deallocate"
    assert entries[0]["command"] == [
        "az", "vm", "deallocate", "--ids",
        "/subscriptions/x/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1",
    ]


def test_plan_refuses_finding_without_resource_id():
    f = _finding("stopped_not_deallocated_vms")
    f["resource_id"] = None
    entries = plan([f])
    assert entries[0]["supported"] is False
    assert "no resource_id" in entries[0]["reason"]


def test_apply_one_skips_when_resource_already_gone(tmp_path):
    entry = plan([_finding("unattached_disks", resource_id="/subscriptions/x/disk1")])[0]
    log_path = str(tmp_path / "remediation_log.json")

    with patch("cloudcost.remediation.executor.resource_exists", return_value=False):
        result = apply_one(entry, log_path=log_path)

    assert result["status"] == "skipped"
    logged = json.loads(open(log_path).read())
    assert len(logged) == 1
    assert logged[0]["status"] == "skipped"


def test_apply_one_never_runs_for_unsupported_entry():
    entry = plan([_finding("not_on_allowlist")])[0]
    try:
        apply_one(entry)
        assert False, "expected ValueError"
    except ValueError:
        pass
