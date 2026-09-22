-- Real check: Azure AI Search services with zero real queries per
-- second over the lookback window -- reserved replica/partition
-- compute billed hourly regardless of query volume. Free tier is $0
-- and excluded upstream. Prices are Azure's real, current per-unit
-- meters (Retail Prices API, 'Azure Cognitive Search' service,
-- eastus): Basic $0.101/hr, Standard $0.348/hr, S2 $1.344/hr,
-- S3 $2.688/hr.
SELECT
    'azure' AS provider,
    resource_id,
    'Azure AI Search' AS service_name,
    ROUND(replicas * partitions * hourly_price_per_unit * 730, 2) AS billed_cost,
    resource_name,
    tier,
    replicas,
    partitions,
    avg_queries_per_second,
    lookback_days,
    tier || ' tier, ' || replicas || ' replica(s) x ' || partitions ||
        ' partition(s), zero real queries over ' || lookback_days || ' days' AS evidence_reason
FROM fact_idle_ai_search
WHERE avg_queries_per_second = 0;
