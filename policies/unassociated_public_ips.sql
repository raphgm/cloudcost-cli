-- Real check: Standard SKU public IPs with no ipConfiguration — reserved,
-- billing, attached to nothing. Standard static public IPs list at
-- roughly $0.005/hour (~$3.65/month) — subject to region and change, a
-- rough order-of-magnitude flag, not an exact invoice figure.
SELECT
    'azure' AS provider,
    resource_id,
    'Public IP Address' AS service_name,
    3.65 AS billed_cost,
    resource_name,
    resource_group,
    sku,
    allocation_method,
    'unassociated public IP (' || sku || ', ' || allocation_method || ')' AS evidence_reason
FROM fact_unassociated_public_ips;
