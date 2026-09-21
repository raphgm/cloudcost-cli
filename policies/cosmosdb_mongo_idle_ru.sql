-- Real check: Cosmos DB for MongoDB API accounts with fixed provisioned
-- throughput and near-zero actual consumption over the lookback
-- window. Same real price as azure.cosmosdb_idle_ru: $0.008/hour per
-- 100 RU/s (Retail Prices API, 'Azure Cosmos DB 100 RU/s' meter) --
-- RU billing is identical across Cosmos APIs, only the CLI surface
-- for managing throughput differs.
SELECT
    'azure' AS provider,
    resource_id,
    'Azure Cosmos DB for MongoDB' AS service_name,
    ROUND((provisioned_ru / 100.0) * 0.008 * 730, 2) AS billed_cost,
    resource_name,
    provisioned_ru,
    total_ru_consumed,
    lookback_days,
    provisioned_ru || ' RU/s provisioned, only ' || ROUND(total_ru_consumed, 0) ||
        ' RU consumed over ' || lookback_days || ' days' AS evidence_reason
FROM fact_cosmosdb_mongo_idle_ru
WHERE provisioned_ru > 0
  AND total_ru_consumed < (provisioned_ru * 0.01);
