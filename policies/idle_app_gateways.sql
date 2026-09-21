-- Real check: Application Gateways where every backend pool has no
-- targets -- reserved, billing hourly, routing traffic to nothing.
-- $0.208/hour = $0.20/hour fixed cost + $0.008/hour per capacity unit
-- (assuming the common default of 1 capacity unit) -- real, current
-- Retail Prices API prices for "Application Gateway Standard v2",
-- excludes data-processing charges (which are $0 at idle).
SELECT
    'azure' AS provider,
    resource_id,
    'Application Gateway' AS service_name,
    ROUND(0.208 * 730, 2) AS billed_cost,
    resource_name,
    resource_group,
    sku,
    'idle Application Gateway, all backend pools empty (' || sku || ' SKU)' AS evidence_reason
FROM fact_idle_app_gateways;
