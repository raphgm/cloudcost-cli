-- Real check: Standard Load Balancers with every backend pool empty —
-- reserved, billing, routing traffic to nothing. $0.025/hour is Azure's
-- documented public base rate for a Standard Load Balancer (excludes
-- per-rule and data-processing charges, which are $0 at idle since
-- nothing is flowing through it) — this is a published list price, not
-- fetched live like the VM sizing check; the Retail Prices API doesn't
-- expose a Load Balancer meter under a name this project could reliably
-- match at the time this was written.
SELECT
    'azure' AS provider,
    resource_id,
    'Load Balancer' AS service_name,
    ROUND(0.025 * 730, 2) AS billed_cost,
    resource_name,
    resource_group,
    sku,
    'idle Load Balancer, all backend pools empty (' || sku || ' SKU)' AS evidence_reason
FROM fact_idle_load_balancers;
