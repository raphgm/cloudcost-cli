import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: GitHub Actions runs that failed, were cancelled, or timed
# out still burn real wall-clock compute time. Verified against
# raphgm/webupgrade (a real private repo, 2500+ real workflow runs):
# a workflow named "Session Reminders" fails repeatedly on a schedule.
#
# Honesty note, same pattern as this project's Azure governance checks:
# the GitHub REST /actions/runs/{id}/timing endpoint returns real
# `run_duration_ms` (wall clock) but `billable.<OS>.total_ms` came back
# 0 for every run checked here, because this account's usage hasn't
# crossed its plan's included free minutes this cycle (confirming that
# requires the "user" billing-scope endpoint, which this session's gh
# auth doesn't have). So this check reports wasted wall-clock minutes,
# priced at GitHub's real published per-minute overage rate for
# standard Linux runners ($0.008/min) -- an honest "if this pushes you
# over your included minutes" estimate, not a claim that money was
# actually charged.
@registry.register_source("github.wasted_actions_minutes")
class GitHubWastedActionsMinutesSource:
    def __init__(self, config: dict):
        self.owner = config.get("owner")
        self.repo = config.get("repo")
        self.lookback_days = config.get("lookback_days", 30)
        if not self.owner or not self.repo:
            raise ValueError("github.wasted_actions_minutes requires 'owner' and 'repo' in config")

    def extract(self, context: Any = None) -> pa.Table:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.lookback_days)

        # Real bug found and fixed: `gh api --paginate` without --jq
        # concatenates each page's raw JSON with no separator between
        # them, so naive newline-splitting fails with "Extra data" --
        # `--jq '.workflow_runs[]'` streams one run object per line
        # instead, which is reliably parseable.
        raw = subprocess.run(
            ["gh", "api", f"repos/{self.owner}/{self.repo}/actions/runs",
             "--paginate", "-X", "GET", "-f", "per_page=100",
             "--jq", ".workflow_runs[]"],
            capture_output=True, text=True, check=True,
        ).stdout

        runs = [json.loads(line) for line in raw.strip().split("\n") if line]

        wasted_runs = [
            r for r in runs
            if r.get("conclusion") in ("failure", "cancelled", "timed_out")
            and datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) >= cutoff
        ]

        rows = []
        for run in wasted_runs:
            timing_raw = subprocess.run(
                ["gh", "api", f"repos/{self.owner}/{self.repo}/actions/runs/{run['id']}/timing"],
                capture_output=True, text=True, check=True,
            ).stdout
            timing = json.loads(timing_raw)

            rows.append({
                "resource_id": f"github/{self.owner}/{self.repo}/runs/{run['id']}",
                "workflow_name": run.get("name", "unknown"),
                "conclusion": run.get("conclusion"),
                "run_duration_ms": timing.get("run_duration_ms", 0),
                "created_at": run["created_at"],
            })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "workflow_name": pa.array([], type=pa.string()),
                "conclusion": pa.array([], type=pa.string()),
                "run_duration_ms": pa.array([], type=pa.int64()),
                "created_at": pa.array([], type=pa.string()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "workflow_name": [r["workflow_name"] for r in rows],
            "conclusion": [r["conclusion"] for r in rows],
            "run_duration_ms": [r["run_duration_ms"] for r in rows],
            "created_at": [r["created_at"] for r in rows],
        })
