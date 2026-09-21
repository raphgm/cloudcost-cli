-- Real check: storage accounts with zero blob containers. Honest note:
-- unlike a disk, VM, or Load Balancer, an empty Standard LRS storage
-- account with nothing stored in it costs essentially nothing -- Azure
-- bills per-GB-stored and per-transaction, not a fixed reservation fee.
-- This is a governance/cleanup finding (account sprawl, orphaned
-- resources from abandoned projects), not a real cost-savings claim --
-- billed_cost is 0 deliberately, not a placeholder that was forgotten.
SELECT
    'azure' AS provider,
    resource_id,
    'Storage Account' AS service_name,
    0.0 AS billed_cost,
    resource_name,
    resource_group,
    sku,
    'empty storage account, 0 containers -- governance cleanup, not a cost-savings finding' AS evidence_reason
FROM fact_empty_storage_accounts;
