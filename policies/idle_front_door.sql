-- Real check: Azure Front Door profiles with zero requests over the
-- lookback window -- a fixed monthly base fee for a CDN/edge profile
-- nothing is routing through. Prices are Azure's real, current
-- "<Tier> Base Fees" meters (Retail Prices API, 'Azure Front Door
-- Service'): Standard $35/month, Premium $412.50/month.
SELECT
    'azure' AS provider,
    resource_id,
    'Azure Front Door' AS service_name,
    CASE
        WHEN sku LIKE '%Premium%' THEN 412.50
        ELSE 35.0
    END AS billed_cost,
    resource_name,
    sku,
    total_requests,
    lookback_days,
    'zero requests over ' || lookback_days || ' days' AS evidence_reason
FROM fact_idle_front_door
WHERE total_requests = 0;
