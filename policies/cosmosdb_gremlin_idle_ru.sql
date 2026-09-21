-- Real check: Cosmos DB for Apache Gremlin (Graph) API accounts with fixed
-- provisioned throughput (RU/s reserved, billed hourly regardless of use)
-- and near-zero actual consumption over the lookback window. Same real
-- price as the SQL, MongoDB, and Cassandra Cosmos checks: $0.008/hour per
-- 100 RU/s (Retail Prices API, 'Azure Cosmos DB 100 RU/s' meter) -- RU
-- billing is identical across Cosmos APIs, but Gremlin uses its own CLI
-- surface (database/graph) for managing throughput. Serverless accounts
-- are excluded upstream.
SELECT
    'azure' AS provider,
    resource_id,
    'Azure Cosmos DB for Gremlin' AS service_name,
    ROUND((provisioned_ru / 100.0) * 0.008 * 730, 2) AS billed_cost,
    resource_name,
    provisioned_ru,
    total_ru_consumed,
    lookback_days,
    provisioned_ru || ' RU/s provisioned, only ' || ROUND(total_ru_consumed, 0) ||
        ' RU consumed over ' || lookback_days || ' days' AS evidence_reason
FROM fact_cosmosdb_gremlin_idle_ru
WHERE provisioned_ru > 0
  AND total_ru_consumed < (provisioned_ru * 0.01);
