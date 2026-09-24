# Changelog

## 0.2.0

### Fixed
- Three checks from PR #24 (`idle_apim`, `idle_fleet_manager`, `idle_managed_hsm`) had SQL policies and tests but no real source file, no `runner.py` registration, and fabricated flat prices. Rebuilt all three against real Azure resources with live pricing (Retail Prices API, or the Key Vault pricing page for Managed HSM, which has no retail meter). Closed #11, #13, #14.
- `rightsizing_utilization` policy had no pipeline config populating its tables — nobody could actually run it. Added `cloudcost.rightsizing-real.yml`; also fixed a source registration mismatch (`azure.metrics` registers itself as `azure.vm_metrics`, not `azure.metrics`).
- README's check-count and table were 10 checks stale (said 49, actually 59). Added the missing rows: `idle_apim`, `idle_fleet_manager`, `idle_managed_hsm`, `idle_health_data_fhir`, `idle_openai_ptu`, `idle_ai_search`, `idle_aml_compute_instance`, `idle_aml_compute_cluster`, `idle_public_ip_prefix`.
- PyPI distribution renamed `cloudcost-cli` -> `cloudcost-finops`: `cloudcost-cli` is already taken by an unrelated project (zedxod/cloudcost). The installed CLI command is unchanged (`cloudcost`).
- `requests` is imported directly (findings notify) but was never declared as a dependency — only worked by accident via a transitive pull. Declared it explicitly.
- `uv_build` defaults the importable module name to the project name; after the PyPI rename that no longer matched the actual `src/cloudcost` package. Pinned via `[tool.uv.build-backend] module-name`.
- Release workflow published to PyPI from all 3 OS matrix runners on every release — the 2nd and 3rd uploads of the same version are rejected by PyPI, failing those jobs. Now publishes once, from `ubuntu-latest`, and skips (rather than failing the whole binary build) if `PYPI_API_TOKEN` isn't configured.

### Added
- New check: idle Azure Health Data Services FHIR service (`idle_health_data_fhir`) — flags FHIR services with zero real API requests, which still bill a fixed hourly Service Runtime fee.
- `cloudcost remediate plan` / `cloudcost remediate apply`: auto-remediation with safety rails. Dry-run by default; `apply` refuses to execute without `--yes`. Deliberately small allow-list (`stopped_not_deallocated_vms`, `unattached_disks`, `unassociated_public_ips`, `old_snapshots`) — every other finding is refused rather than guessed at. Every execution is written to `data/remediation_log.json` as an audit trail, and re-checks the resource still exists before acting.
