-- Real check: Traffic Manager profiles with monitored endpoints and
-- zero real DNS queries over the lookback window -- health-check fees
-- bill per endpoint monthly regardless of query volume. Prices are
-- Azure's real, current health-check meters (Retail Prices API,
-- 'Traffic Manager' service): $0.36/month per Azure endpoint,
-- $0.54/month per non-Azure endpoint.
SELECT
    'azure' AS provider,
    resource_id,
    'Traffic Manager Profile' AS service_name,
    ROUND(azure_endpoint_count * 0.36 + non_azure_endpoint_count * 0.54, 2) AS billed_cost,
    resource_name,
    azure_endpoint_count,
    non_azure_endpoint_count,
    total_queries,
    lookback_days,
    (azure_endpoint_count + non_azure_endpoint_count) || ' endpoint(s) monitored, zero DNS queries over ' ||
        lookback_days || ' days' AS evidence_reason
FROM fact_idle_traffic_manager
WHERE total_queries = 0;
