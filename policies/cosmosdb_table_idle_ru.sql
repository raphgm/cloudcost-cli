-- Real check: Cosmos DB for Table API tables with fixed provisioned
-- throughput and near-zero actual consumption. Same real price as
-- every other Cosmos API check in this project: $0.008/hour per 100
-- RU/s (Retail Prices API, 'Azure Cosmos DB 100 RU/s' meter) -- RU
-- billing is identical across Cosmos APIs, only the CLI/resource
-- surface (table vs database/keyspace/graph) differs.
SELECT
    'azure' AS provider,
    resource_id,
    'Azure Cosmos DB for Table' AS service_name,
    ROUND((provisioned_ru / 100.0) * 0.008 * 730, 2) AS billed_cost,
    resource_name,
    provisioned_ru,
    total_ru_consumed,
    lookback_days,
    provisioned_ru || ' RU/s provisioned, only ' || ROUND(total_ru_consumed, 0) ||
        ' RU consumed over ' || lookback_days || ' days' AS evidence_reason
FROM fact_cosmosdb_table_idle_ru
WHERE provisioned_ru > 0
  AND total_ru_consumed < (provisioned_ru * 0.01);
