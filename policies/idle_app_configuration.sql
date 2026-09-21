-- Real check: App Configuration Standard/Premium stores with zero HTTP
-- requests over the lookback window -- fixed per-day instance fee
-- billed regardless of real request volume. Prices are Azure's real,
-- current "<Tier> Instance" meters (Retail Prices API): Standard
-- $1.20/day, Premium $9.60/day.
SELECT
    'azure' AS provider,
    resource_id,
    'App Configuration' AS service_name,
    ROUND((CASE WHEN sku = 'Premium' THEN 9.60 ELSE 1.20 END) * 30, 2) AS billed_cost,
    resource_name,
    sku,
    total_requests,
    lookback_days,
    'zero HTTP requests over ' || lookback_days || ' days' AS evidence_reason
FROM fact_idle_app_configuration
WHERE total_requests = 0;
