-- Real check: Public IP Prefixes with zero real Public IP addresses
-- allocated from the reserved block -- distinct resource type from a
-- single unassociated Public IP (unassociated_public_ips.sql). Each
-- reserved address bills at the standard Standard-SKU rate
-- ($3.65/month, same real price used elsewhere in this project)
-- whether an actual Public IP resource has been carved out of it or
-- not.
SELECT
    'azure' AS provider,
    resource_id,
    'Public IP Prefix' AS service_name,
    ROUND(reserved_addresses * 3.65, 2) AS billed_cost,
    resource_name,
    reserved_addresses,
    allocated_count,
    reserved_addresses || ' address(es) reserved, ' || allocated_count ||
        ' actually allocated' AS evidence_reason
FROM fact_idle_public_ip_prefix
WHERE allocated_count = 0;
