-- Real check: Azure Bastion hosts with zero sessions over the lookback
-- window -- a fixed-cost jump host reserved but unused. $0.19/hour is
-- Azure's real, current Basic SKU "Gateway" price (Retail Prices API,
-- serviceName 'Azure Bastion', meterName 'Basic Gateway', eastus).
-- Standard/Premium SKUs cost more ($0.29/$0.45) and aren't priced here yet.
SELECT
    'azure' AS provider,
    resource_id,
    'Azure Bastion' AS service_name,
    CASE sku
        WHEN 'Standard' THEN ROUND(0.29 * 730, 2)
        WHEN 'Premium' THEN ROUND(0.45 * 730, 2)
        ELSE ROUND(0.19 * 730, 2)
    END AS billed_cost,
    resource_name,
    total_sessions,
    lookback_days,
    'zero bastion sessions over ' || lookback_days || ' days' AS evidence_reason
FROM fact_idle_bastion
WHERE total_sessions = 0;
