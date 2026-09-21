# Contributing to CloudCost CLI

Thanks for helping. This note is the missing map for adding a FinOps check. Existing checks all follow the same four-file pattern; new ones should too.

Python 3.13+ and `uv` are required. From a clone:

```bash
uv venv
uv pip install -e .
source .venv/bin/activate
```

## The 4-file pattern

Every check is four pieces that share one name:

| Piece | Path | Role |
| --- | --- | --- |
| Source plugin | `src/cloudcost/sources/<provider>/<check_name>.py` | Extract live inventory/metrics into a PyArrow table |
| SQL policy | `policies/<check_name>.sql` | Turn that table into findings with a dollar amount |
| Live pipeline | `cloudcost.<check_name>-real.yml` | Wire the source into DuckDB and point `policy run` at the SQL |
| Registration | `src/cloudcost/engine/runner.py` | One extra `import` so the plugin is loaded |

Naming is snake_case in Python and SQL filenames (`idle_bastion`), kebab-case in pipeline filenames and policy `name` fields (`idle-bastion`). The source type string registered with `@registry.register_source` is `<provider>.<check_name>` with dots and underscores, e.g. `azure.idle_bastion`.

Look at `idle_bastion` if you want a complete existing example:

- `src/cloudcost/sources/azure/idle_bastion.py`
- `policies/idle_bastion.sql`
- `cloudcost.idle-bastion-real.yml`
- the `import cloudcost.sources.azure.idle_bastion` line in `runner.py`

## Minimal worked example

Suppose you want a check that flags idle Azure NAT gateways. The four files look like this.

### 1. Source plugin

```python
# src/cloudcost/sources/azure/idle_nat_gateways.py
import json
import subprocess
from typing import Any

import pyarrow as pa

from cloudcost.core.registry import registry


@registry.register_source("azure.idle_nat_gateways")
class AzureIdleNatGatewaysSource:
    def __init__(self, config: dict):
        self.resource_group = config.get("resource_group")
        if not self.resource_group:
            raise ValueError("azure.idle_nat_gateways requires 'resource_group' in config")

    def extract(self, context: Any = None) -> pa.Table:
        raw = subprocess.run(
            [
                "az", "network", "nat", "gateway", "list",
                "--resource-group", self.resource_group,
                "-o", "json",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        items = json.loads(raw)
        # Build a table with at least resource_id and the metric the policy filters on.
        # Query live prices here (or in the policy comments) — do not invent a rate card.
        return pa.table({
            "resource_id": [i["id"].lower() for i in items],
            "resource_name": [i["name"] for i in items],
        })
```

`extract` must return a PyArrow table. Empty results should still return a typed empty table so DuckDB can create the destination schema.

### 2. SQL policy

```sql
-- policies/idle_nat_gateways.sql
-- billed_cost must come from a live price quote (Azure Retail Prices API
-- or AWS Price List API), documented in this comment with serviceName,
-- meterName, region, and the date you fetched it.
SELECT
    'azure' AS provider,
    resource_id,
    'NAT Gateway' AS service_name,
    billed_cost,
    resource_name,
    evidence_reason
FROM fact_idle_nat_gateways
WHERE <idle condition>;
```

The pipeline load table name (`fact_idle_nat_gateways` above) must match what the YAML writes.

### 3. Live pipeline config

```yaml
# cloudcost.idle-nat-gateways-real.yml
version: "1"

pipeline:
  name: idle-nat-gateways-real-test
  mode: incremental
  timezone: UTC

sources:
  - name: nat_metrics
    type: azure.idle_nat_gateways
    config:
      resource_group: your-test-rg

destinations:
  - name: local_duckdb
    type: duckdb
    config:
      path: ./data/idle-nat-gateways-real.duckdb

loads:
  - input: nat_metrics
    destination: local_duckdb
    table: fact_idle_nat_gateways
    mode: overwrite

policies:
  - name: idle-nat-gateways
    type: sql
    query_file: policies/idle_nat_gateways.sql
    severity: medium
```

### 4. Register the source

Add one import next to the other Azure plugins in `src/cloudcost/engine/runner.py`, inside the existing `try` block:

```python
import cloudcost.sources.azure.idle_nat_gateways
```

That import is what runs `@registry.register_source`. If you skip it, `cloudcost sync` will fail with an unknown source type.

## Live-pricing convention

Do not commit a homemade price table. Quote a real catalog:

- Azure: [Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices)
- AWS: [Price List API](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-changes.html)

Record the query you used (service name, meter, region) and the date in a comment next to `billed_cost`. If a policy currently embeds a numeric rate (for example `policies/idle_bastion.sql`), that number must still be a snapshot of a live quote with the lookup written above it — not an estimate.

Prefer fetching the price in the source plugin at extract time when the SKU varies per row. A documented snapshot in SQL is acceptable only when the meter is a single well-known SKU and the comment names the exact Retail Prices / Price List query.

## Verify a check for real

Unit tests are not a substitute here. Each check is confirmed against a real cloud resource:

1. Create the resource in a throwaway resource group (or reuse `cost-compare-3day-rg` if you have access to the existing test account).
2. Wait long enough for the metric window you chose (`lookback_days`, activity counters, etc.).
3. Run the pipeline:

   ```bash
   cloudcost validate cloudcost.<check_name>-real.yml
   cloudcost sync cloudcost.<check_name>-real.yml
   cloudcost policy run cloudcost.<check_name>-real.yml
   cloudcost findings list
   ```

4. Confirm the finding exists and the `$` amount matches the live price quote for that SKU, not a rounded guess.
5. Tear the resource down so the test account does not keep billing.

`policy run` reads the DuckDB path from the first `type: duckdb` destination in that same YAML. Do not assume `data/cloudcost.duckdb`.

## Pull requests

- Keep the change to one check or one tightly related fix.
- Include the four files (or a documented reason a file is not needed).
- In the PR body, write the exact commands you ran and the finding amount you observed.
- Do not add dependencies unless the check cannot call the provider CLI or official SDK already in `pyproject.toml`.
