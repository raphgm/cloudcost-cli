-- Real check: Network Security Groups attached to nothing. Honest note:
-- NSGs are free in Azure -- this is a governance/cleanup finding
-- (resource sprawl, orphaned artifacts from deleted VMs/subnets), not a
-- cost-savings claim. billed_cost is 0 deliberately.
SELECT
    'azure' AS provider,
    resource_id,
    'Network Security Group' AS service_name,
    0.0 AS billed_cost,
    resource_name,
    resource_group,
    'orphaned NSG, attached to no subnet or network interface -- governance cleanup, not a cost-savings finding' AS evidence_reason
FROM fact_orphaned_nsgs;
