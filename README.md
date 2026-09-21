# CloudCost CLI

**Enterprise Multi-Cloud FinOps Data Platform**

CloudCost CLI is a provider-neutral, open-source FinOps data platform designed to collect, normalize, enrich, analyze, and govern cloud financial and infrastructure data across AWS, Azure, GCP, OCI, and Alibaba Cloud.

## Key Features
- **Declarative YAML Pipelines**: Define your extraction, transformation, and loading in a single `cloudcost.yml` file.
- **Apache Arrow Data Plane**: Lightning-fast, in-memory data movement.
- **Bring-Your-Own Warehouse**: Load normalized billing data directly into DuckDB, PostgreSQL, or Google BigQuery.
- **SQL-First Governance Engine**: Write FinOps policies (like identifying unallocated costs or zero utilization resources) using standard SQL, producing structured findings.
- **Native Cloud Providers**: Direct integration with `boto3`, `azure-storage-blob`, `oci`, and `oss2`.

## Install (macOS Apple Silicon)

A standalone binary — no Python, no `pip`, no `uv`, no dependency management at all:

```bash
curl -L https://github.com/raphgm/cloudcost-cli/releases/download/v0.1.0/cloudcost-macos-arm64 -o cloudcost
chmod +x cloudcost
./cloudcost --help
```

This is currently the only prebuilt binary — macOS arm64 (Apple Silicon) only, built and verified on that platform. No Linux, Windows, or Intel-Mac build exists yet.

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

## Architecture

CloudCost utilizes a layered plugin architecture. The CLI is built on **Typer** and **Rich**. Data is extracted via provider plugins directly into **PyArrow** tables, transformed in-memory, and synced to **DuckDB** or other data warehouses. Policies are executed directly against the warehouse to generate evidence-backed FinOps findings.

`cloudcost policy run` reads its DuckDB path from the pipeline's own `destinations` config (the first `type: duckdb` entry) rather than a hardcoded default — this was a real bug until 2026-09-20 (`policy run` would fail with "database does not exist" against any pipeline that didn't name its file exactly `data/cloudcost.duckdb`), found and fixed while testing this tool against a real Azure account.
