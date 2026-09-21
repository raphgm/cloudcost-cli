-- Real check: Azure Cache for Redis instances with sustained low
-- connected-client counts -- reserved compute for a cache nothing is
-- actually connecting to. $0.022/hour is Azure's real, current Basic C0
-- price (Retail Prices API, productName 'Azure Redis Cache Basic') --
-- higher tiers cost more and aren't priced here yet, so this is a
-- placeholder impact estimate for non-Basic instances.
SELECT
    'azure' AS provider,
    resource_id,
    'Azure Cache for Redis' AS service_name,
    ROUND(0.022 * 730, 2) AS billed_cost,
    resource_name,
    ROUND(AVG(avg_connected_clients), 2) AS avg_connected_clients,
    'sustained low connected-client count (' || ROUND(AVG(avg_connected_clients), 1) || ' avg)' AS evidence_reason
FROM fact_redis_idle_metrics
GROUP BY resource_id, resource_name
HAVING AVG(avg_connected_clients) < 1.0;
