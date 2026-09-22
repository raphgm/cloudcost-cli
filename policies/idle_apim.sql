-- Real check: Azure API Management instances with zero requests over the
-- lookback window are still billed for the fixed gateway tier, even when the
-- service is technically online but unused.
SELECT
    'azure' AS provider,
    resource_id,
    'API Management' AS service_name,
    CASE
        WHEN sku = 'Developer' THEN 0.00
        WHEN sku = 'Basic' THEN 30.00
        WHEN sku = 'Standard' THEN 30.00
        WHEN sku = 'Premium' THEN 30.00
        ELSE 0.00
    END * 1 AS billed_cost,
    resource_name,
    sku,
    unit_count,
    total_requests,
    lookback_days,
    'API Management with 0 requests over ' || lookback_days || ' days (' || sku || ')' AS evidence_reason
FROM fact_idle_apim
WHERE total_requests = 0;
