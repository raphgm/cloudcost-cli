-- Real check: Azure Data Explorer cluster with zero ingestion and zero
-- queries over the lookback window while its reserved instance count stays
-- active and billed hourly. This is a genuine reserved-capacity cost pattern
-- rather than a transient idle condition.
SELECT
    'azure' AS provider,
    resource_id,
    'Azure Data Explorer Cluster' AS service_name,
    ROUND(instance_count * hourly_price_per_instance * 730, 2) AS billed_cost,
    resource_name,
    sku,
    instance_count,
    total_ingestion_mb,
    total_queries,
    lookback_days,
    'cluster with 0 ingestion and 0 queries over ' || lookback_days || ' days (' || sku || ')' AS evidence_reason
FROM fact_idle_kusto_cluster
WHERE total_ingestion_mb = 0 AND total_queries = 0;
