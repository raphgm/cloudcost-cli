# CloudCost CLI

**Enterprise Multi-Cloud FinOps Data Platform**

CloudCost CLI is a provider-neutral, open-source FinOps data platform designed to collect, normalize, enrich, analyze, and govern cloud financial and infrastructure data across AWS, Azure, GCP, OCI, and Alibaba Cloud.

## Key Features
- **Declarative YAML Pipelines**: Define your extraction, transformation, and loading in a single `cloudcost.yml` file.
- **Apache Arrow Data Plane**: Lightning-fast, in-memory data movement.
- **Bring-Your-Own Warehouse**: Load normalized billing data directly into DuckDB, PostgreSQL, or Google BigQuery.
- **SQL-First Governance Engine**: Write FinOps policies (like identifying unallocated costs or zero utilization resources) using standard SQL, producing structured findings.
- **Live pricing, not hardcoded tables**: every check that needs a price fetches it from the provider's own live pricing API (Azure Retail Prices API today) at run time, not a rate card baked into the code that goes stale.
- **Native Cloud Providers**: Direct integration with `boto3`, `azure-storage-blob`, `oci`, and `oss2`.

## Real, individually-verified checks

Every check below was built the same way: create the actual cloud resource, run `cloudcost sync` + `policy run` + `findings list`, confirm the real dollar amount, then tear the resource down. No synthetic fixtures, no invented prices. See [CONTRIBUTING.md](CONTRIBUTING.md) for the exact pattern and how to add your own.

**Compute**
- Stopped-but-not-deallocated VMs (still billing) — `stopped_not_deallocated_vms`
- VM rightsizing via CPU/network/disk metrics + live pricing — `vm_sizing_recommendation`, `rightsizing_utilization`
- Idle VM Scale Set (fixed instance count, low CPU) — `idle_vmss`
- Idle AKS node pool (control plane is free; the node VMs aren't) — `aks_idle_nodepool`
- Idle Container Instance (restartPolicy=Always, near-zero CPU) — `idle_container_instances`
- Idle Batch pool (dedicated nodes, zero active jobs) — `idle_batch_pool`
- Zero-utilization resources (general) — `zero_utilization`

**Networking**
- Unattached managed disks — `unattached_disks`
- Unassociated public IPs — `unassociated_public_ips`
- Idle load balancers / NAT gateways / Application Gateways — `idle_load_balancers`, `idle_nat_gateways`, `idle_app_gateways`
- Idle Azure Firewall — `idle_firewall`
- Idle Azure Bastion (zero sessions) — `idle_bastion`
- Idle Private Endpoints (zero traffic) — `idle_private_endpoints`
- Orphaned NSGs — `orphaned_nsgs`
- Idle Front Door profile — `idle_front_door`
- Idle Traffic Manager endpoint monitoring — `idle_traffic_manager`
- Idle/orphaned DNS zones — `idle_dns_zone`

**Data & storage**
- Old/orphaned disk snapshots — `old_snapshots`
- Premium disk downsize opportunities — `premium_disk_downsize`
- Empty storage accounts — `empty_storage_accounts`
- Log Analytics Commitment Tier over-reservation — `log_analytics_idle_commitment`

**Databases & messaging**
- Azure SQL DTU underutilization — `sql_dtu_underutilized`
- Idle Cosmos DB provisioned throughput — `cosmosdb_idle_ru`
- Idle PostgreSQL / MySQL Flexible Server — `postgres_idle_flexible`, `mysql_idle_flexible`
- Idle Redis Cache — `redis_idle`
- Idle Event Hubs Namespace (Standard) — `idle_eventhub`
- Idle Service Bus Namespace (Premium) — `idle_servicebus_premium`

**App platform**
- Idle App Service Plans — `idle_app_service_plans`
- Idle Static Web App (Standard) — `idle_static_web_app`
- Idle App Configuration store — `idle_app_configuration`
- Idle SignalR Service — `idle_signalr`
- Idle Managed Grafana — `idle_managed_grafana`
- Idle Container Registries — `idle_container_registries`

**Governance**
- Untagged resources — `untagged_resources`
- Unallocated costs — `unallocated_costs`

**Beyond cloud infra**
- GitHub Actions wasted CI minutes (failed/cancelled workflow runs) — `github_wasted_actions_minutes`

## Install (prebuilt binaries)

Standalone binaries — no Python, no `pip`, no `uv`, no dependency management at all. Each is built and verified (`--help` runs clean) on its own native CI runner (macOS 14 arm64, ubuntu-latest, windows-latest via GitHub Actions).

```bash
# macOS (Apple Silicon) — Homebrew, handles download/chmod/PATH for you
brew install raphgm/tap/cloudcost
cloudcost --help
```

```bash
# macOS (Apple Silicon) — or download the binary directly
curl -L https://github.com/raphgm/cloudcost-cli/releases/download/v0.1.0/cloudcost-macos-arm64 -o cloudcost
chmod +x cloudcost
./cloudcost --help
```

```bash
# Linux (x86_64)
curl -L https://github.com/raphgm/cloudcost-cli/releases/download/v0.1.0/cloudcost-linux-x86_64 -o cloudcost
chmod +x cloudcost
./cloudcost --help
```

```powershell
# Windows (x86_64) — PowerShell
Invoke-WebRequest https://github.com/raphgm/cloudcost-cli/releases/download/v0.1.0/cloudcost-windows-x86_64.exe -OutFile cloudcost.exe
.\cloudcost.exe --help
```

Intel Mac isn't built yet. New binaries build automatically via `.github/workflows/build-release.yml` on every GitHub release, or can be triggered manually via `workflow_dispatch`.

## Building from source

For other platforms, or if you're contributing. Requires Python 3.13+ and `uv`:

```bash
uv venv
uv pip install -e .
source .venv/bin/activate
```

## Quick Start

1. Initialize a new project:
```bash
cloudcost init
```

2. Validate your pipeline configuration:
```bash
cloudcost validate cloudcost.yml
```

3. Sync data across your clouds to your warehouse:
```bash
cloudcost sync cloudcost.yml
```

4. Run your SQL governance policies:
```bash
cloudcost policy run cloudcost.yml
```

5. View your optimization findings:
```bash
cloudcost findings list
```

## Mapping a real cloud source to the FOCUS schema

`focus.normalize` doesn't guess your source's column names — declare the mapping explicitly in the transform's `config`, since every provider's raw export uses different names (Azure Cost Management's `azure.cost_export` source, for example, produces `ServiceName`/`PreTaxCost`, not the FOCUS-style `service_name`/`billed_cost` the bundled policies expect):

```yaml
transforms:
  - name: normalize_costs
    type: focus.normalize
    input: azure_billing
    config:
      provider: azure
      column_map:
        ServiceName: service_name
        PreTaxCost: billed_cost
        InstanceId: resource_id
        ResourceGroup: resource_group
        UsageDateTime: usage_date
```

This was verified end-to-end against a real Azure Cost Management export (215 real cost line items, `cloudcost sync` + `cloudcost policy run` both succeeding and producing real findings) — see `cloudcost.azure-real.yml` for the full working example. AWS/OCI/Alibaba each need their own `column_map` matched to their real export schema; none of those have been verified against live data yet.

**Independently re-verified from a completely fresh clone** (new `git clone`, new `uv venv`, new `uv pip install -e .`, no leftover state) against the same live export, confirming the fix isn't an artifact of the environment it was written in:

```text
Extracting from source: azure_billing
  -> Extracted 215 rows
Transforming data: normalize_costs
  -> Transformed 215 rows
Loading data to destination: local_duckdb
  -> Loaded 215 rows into local_duckdb

Evaluating policy: unallocated-costs
  -> Generated 0 findings.
Evaluating policy: zero-utilization
  -> Generated 6 findings.
```

Real breakdown from that data: **$50.50 total** across the resource group's lifetime, with **Azure Bastion alone at $26.02 — 52% of total spend** — the same always-on-cost-concentration pattern flagged in the [Open Cloud Cost Intelligence](https://github.com/raphgm/cloud-cost-intelligence) project, now caught independently by this tool's `zero-utilization` policy against Virtual Machines (6 findings, $0.21–$1.00 each).

![Daily billed cost and cost by service, charted from the real DuckDB output of this pipeline](docs/real-azure-test-results.png)

## Contributing

Want to add a check for AWS, GCP, or another Azure service? See [CONTRIBUTING.md](CONTRIBUTING.md) for the 4-file pattern every check follows, and the [open issues](https://github.com/raphgm/cloudcost-cli/issues) for good starting points (AWS/GCP parity, safe auto-remediation, PyPI packaging, a proper test suite).

## Architecture

CloudCost utilizes a layered plugin architecture. The CLI is built on **Typer** and **Rich**. Data is extracted via provider plugins directly into **PyArrow** tables, transformed in-memory, and synced to **DuckDB** or other data warehouses. Policies are executed directly against the warehouse to generate evidence-backed FinOps findings.

`cloudcost policy run` reads its DuckDB path from the pipeline's own `destinations` config (the first `type: duckdb` entry) rather than a hardcoded default — this was a real bug until 2026-09-20 (`policy run` would fail with "database does not exist" against any pipeline that didn't name its file exactly `data/cloudcost.duckdb`), found and fixed while testing this tool against a real Azure account.
