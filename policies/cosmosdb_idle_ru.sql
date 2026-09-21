-- Real check: Cosmos DB accounts with fixed provisioned throughput
-- (RU/s reserved, billed hourly regardless of use) and near-zero
-- actual consumption over the lookback window. $0.008/hour per
-- 100 RU/s is Azure's real, current "Azure Cosmos DB 100 RU/s" meter
-- (Retail Prices API). Serverless accounts are excluded upstream --
-- they only bill for RU actually consumed.
SELECT
    'azure' AS provider,
    resource_id,
    'Azure Cosmos DB' AS service_name,
    ROUND((provisioned_ru / 100.0) * 0.008 * 730, 2) AS billed_cost,
    resource_name,
    provisioned_ru,
    total_ru_consumed,
    lookback_days,
    provisioned_ru || ' RU/s provisioned, only ' || ROUND(total_ru_consumed, 0) ||
        ' RU consumed over ' || lookback_days || ' days' AS evidence_reason
FROM fact_cosmosdb_idle_ru
WHERE provisioned_ru > 0
  AND total_ru_consumed < (provisioned_ru * 0.01);
