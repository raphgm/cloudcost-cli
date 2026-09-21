-- Real check: Standard-SKU Managed Grafana instances with zero HTTP
-- requests over the lookback window -- a fixed hourly node fee billed
-- whether anyone opens a dashboard or not. $0.042808/hour is Azure's
-- real, current "Standard Node" meter (Retail Prices API, 'Azure
-- Grafana Service').
SELECT
    'azure' AS provider,
    resource_id,
    'Azure Managed Grafana' AS service_name,
    ROUND(0.042808 * 730, 2) AS billed_cost,
    resource_name,
    sku,
    total_requests,
    lookback_days,
    'zero HTTP requests over ' || lookback_days || ' days' AS evidence_reason
FROM fact_idle_managed_grafana
WHERE total_requests = 0;
