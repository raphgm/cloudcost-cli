# CloudCost CLI

**Enterprise Multi-Cloud FinOps Data Platform**

CloudCost CLI is a provider-neutral, open-source FinOps data platform designed to collect, normalize, enrich, analyze, and govern cloud financial and infrastructure data across AWS, Azure, GCP, OCI, and Alibaba Cloud.

## Key Features
- **Declarative YAML Pipelines**: Define your extraction, transformation, and loading in a single `cloudcost.yml` file.
- **Apache Arrow Data Plane**: Lightning-fast, in-memory data movement.
- **Bring-Your-Own Warehouse**: Load normalized billing data directly into DuckDB, PostgreSQL, or Google BigQuery.
- **SQL-First Governance Engine**: Write FinOps policies (like identifying unallocated costs or zero utilization resources) using standard SQL, producing structured findings.
- **Native Cloud Providers**: Direct integration with `boto3`, `azure-storage-blob`, `oci`, and `oss2`.

## Installation

Ensure you have Python 3.13+ and `uv` installed, then run:

```bash
uv pip install -e .
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

## Architecture

CloudCost utilizes a layered plugin architecture. The CLI is built on **Typer** and **Rich**. Data is extracted via provider plugins directly into **PyArrow** tables, transformed in-memory, and synced to **DuckDB** or other data warehouses. Policies are executed directly against the warehouse to generate evidence-backed FinOps findings.
