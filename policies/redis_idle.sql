-- Real check: Azure Cache for Redis instances with sustained low
-- connected-client counts -- reserved compute for a cache nothing is
-- actually connecting to. Price is fetched live per instance's real
-- tier/SKU (e.g. "Standard C1", "Premium P2") via the Retail Prices
-- API, fixing a real bug where every tier was previously priced as
-- Basic C0 regardless of its actual SKU.
SELECT
    'azure' AS provider,
    resource_id,
    'Azure Cache for Redis' AS service_name,
    ROUND(AVG(hourly_price) * 730, 2) AS billed_cost,
    resource_name,
    ROUND(AVG(avg_connected_clients), 2) AS avg_connected_clients,
    'sustained low connected-client count (' || ROUND(AVG(avg_connected_clients), 1) || ' avg)' AS evidence_reason
FROM fact_redis_idle_metrics
WHERE hourly_price > 0
GROUP BY resource_id, resource_name
HAVING AVG(avg_connected_clients) < 1.0;
