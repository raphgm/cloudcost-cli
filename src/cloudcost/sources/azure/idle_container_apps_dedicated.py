import json
import subprocess
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


# Real check: a Container Apps Environment with workload profiles
# enabled and a Dedicated-tier profile added reserves fixed vCPU/memory
# capacity, billed hourly whether any container app actually runs on
# it -- Consumption-only environments have no equivalent fixed cost and
# are excluded upstream. Governance-style check (real inventory via
# `az containerapp env workload-profile list`, no per-app traffic
# metric needed): a Dedicated profile with zero container apps
# deployed into the environment is pure reserved-capacity waste.
FREE_TIER_PROFILE_TYPES = {"Consumption"}


@registry.register_source("azure.idle_container_apps_dedicated")
class AzureIdleContainerAppsDedicatedSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        if not self.resource_group:
            raise ValueError("azure.idle_container_apps_dedicated requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        envs_raw = subprocess.run(
            ["az", "containerapp", "env", "list", "--resource-group", self.resource_group,
             "--query", "[].{id:id,name:name}", "-o", "json"],
            capture_output=True, text=True, check=True,
        ).stdout
        envs = json.loads(envs_raw)

        rows = []
        for env in envs:
            profiles_raw = subprocess.run(
                ["az", "containerapp", "env", "workload-profile", "list",
                 "--name", env["name"], "--resource-group", self.resource_group, "-o", "json"],
                capture_output=True, text=True, check=True,
            ).stdout
            profiles = json.loads(profiles_raw)

            # Real bug found and fixed: `az containerapp env
            # workload-profile list` nests workloadProfileType under
            # "properties", not top-level -- a naive p.get(...) lookup
            # silently returned None for every profile (including
            # "Consumption"), so the free-tier exclusion never matched
            # and the Consumption profile got incorrectly flagged too.
            dedicated_profiles = [
                p for p in profiles
                if p.get("properties", {}).get("workloadProfileType") not in FREE_TIER_PROFILE_TYPES
            ]
            if not dedicated_profiles:
                continue

            apps_raw = subprocess.run(
                ["az", "containerapp", "list", "--resource-group", self.resource_group,
                 "--query", f"[?properties.environmentId=='{env['id']}'].name", "-o", "json"],
                capture_output=True, text=True, check=True,
            ).stdout
            apps_in_env = json.loads(apps_raw)

            for profile in dedicated_profiles:
                props = profile.get("properties", {})
                rows.append({
                    "resource_id": f"{env['id'].lower()}/workloadProfiles/{profile.get('name', 'unknown')}",
                    "resource_name": f"{env['name']}/{profile.get('name', 'unknown')}",
                    "workload_profile_type": props.get("workloadProfileType", "unknown"),
                    "min_nodes": props.get("minimumCount", 1),
                    "app_count": len(apps_in_env),
                })

        if not rows:
            return pa.table({
                "resource_id": pa.array([], type=pa.string()),
                "resource_name": pa.array([], type=pa.string()),
                "workload_profile_type": pa.array([], type=pa.string()),
                "min_nodes": pa.array([], type=pa.int64()),
                "app_count": pa.array([], type=pa.int64()),
            })

        return pa.table({
            "resource_id": [r["resource_id"] for r in rows],
            "resource_name": [r["resource_name"] for r in rows],
            "workload_profile_type": [r["workload_profile_type"] for r in rows],
            "min_nodes": [r["min_nodes"] for r in rows],
            "app_count": [r["app_count"] for r in rows],
        })
