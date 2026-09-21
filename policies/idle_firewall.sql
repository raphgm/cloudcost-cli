-- Real check: Azure Firewall deployments with zero data processed over
-- the lookback window -- a fixed hourly deployment charge for a firewall
-- nothing is routing through. Prices are Azure's real, current
-- "<Tier> Deployment" meters (Retail Prices API, serviceName
-- 'Azure Firewall', eastus): Basic $0.395/hr, Standard $1.25/hr,
-- Premium $1.75/hr.
SELECT
    'azure' AS provider,
    resource_id,
    'Azure Firewall' AS service_name,
    CASE tier
        WHEN 'Basic' THEN ROUND(0.395 * 730, 2)
        WHEN 'Premium' THEN ROUND(1.75 * 730, 2)
        ELSE ROUND(1.25 * 730, 2)
    END AS billed_cost,
    resource_name,
    total_bytes_processed,
    lookback_days,
    'zero data processed over ' || lookback_days || ' days' AS evidence_reason
FROM fact_idle_firewall
WHERE total_bytes_processed = 0;
