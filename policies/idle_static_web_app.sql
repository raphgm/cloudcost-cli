-- Real check: Standard-tier Static Web Apps with zero site hits over
-- the lookback window -- flat $9/month app fee billed regardless of
-- real traffic. Free tier is $0 and excluded upstream. Price is
-- Azure's real, current "Standard App" meter (Retail Prices API,
-- 'Azure App Service Static Web Apps').
SELECT
    'azure' AS provider,
    resource_id,
    'Azure Static Web Apps' AS service_name,
    9.0 AS billed_cost,
    resource_name,
    sku,
    total_hits,
    lookback_days,
    'zero site hits over ' || lookback_days || ' days' AS evidence_reason
FROM fact_idle_static_web_app
WHERE total_hits = 0;
