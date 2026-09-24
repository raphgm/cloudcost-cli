import datetime
import json
import os
import subprocess
from typing import Any

from cloudcost.remediation.registry import get_action


def resource_exists(resource_id: str) -> bool:
    result = subprocess.run(
        ["az", "resource", "show", "--ids", resource_id, "-o", "none"],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def plan(findings: list[dict]) -> list[dict[str, Any]]:
    """Build a dry-run remediation plan for a list of findings. Never executes anything."""
    entries = []
    for finding in findings:
        action = get_action(finding["policy_name"])
        if action is None:
            entries.append({
                "finding_id": finding["finding_id"],
                "resource_id": finding.get("resource_id"),
                "policy_name": finding["policy_name"],
                "supported": False,
                "reason": "not on the auto-remediation allow-list",
            })
            continue
        if not finding.get("resource_id"):
            entries.append({
                "finding_id": finding["finding_id"],
                "resource_id": None,
                "policy_name": finding["policy_name"],
                "supported": False,
                "reason": "finding has no resource_id to act on",
            })
            continue
        command = [c.format(id=finding["resource_id"]) for c in action.command]
        entries.append({
            "finding_id": finding["finding_id"],
            "resource_id": finding["resource_id"],
            "policy_name": finding["policy_name"],
            "supported": True,
            "action": action.action,
            "risk": action.risk,
            "description": action.description,
            "command": command,
        })
    return entries


def apply_one(entry: dict[str, Any], log_path: str = "data/remediation_log.json") -> dict[str, Any]:
    """Execute a single planned entry for real. Caller must have already confirmed with the user."""
    if not entry["supported"]:
        raise ValueError(f"finding {entry['finding_id']} is not remediable: {entry['reason']}")

    result_entry = {
        "finding_id": entry["finding_id"],
        "resource_id": entry["resource_id"],
        "policy_name": entry["policy_name"],
        "action": entry["action"],
        "command": entry["command"],
        "executed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    if not resource_exists(entry["resource_id"]):
        result_entry["status"] = "skipped"
        result_entry["message"] = "resource no longer exists (already gone)"
        _append_log(log_path, result_entry)
        return result_entry

    proc = subprocess.run(entry["command"], capture_output=True, text=True)
    if proc.returncode == 0:
        result_entry["status"] = "success"
        result_entry["message"] = proc.stdout.strip()
    else:
        result_entry["status"] = "failed"
        result_entry["message"] = proc.stderr.strip()

    _append_log(log_path, result_entry)
    return result_entry


def _append_log(log_path: str, entry: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    existing = []
    if os.path.exists(log_path):
        try:
            with open(log_path, "r") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            existing = []
    existing.append(entry)
    with open(log_path, "w") as f:
        json.dump(existing, f, indent=2, default=str)
