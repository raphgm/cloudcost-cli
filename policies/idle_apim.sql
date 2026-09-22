-- Real check: Azure API Management instances with zero requests over the
-- lookback window are still billed for the reserved gateway tier, even
-- when the service is technically online but unused. Price fetched live
-- per real tier via the Retail Prices API. Consumption tier is
-- pay-per-call and has no equivalent waste, excluded upstream.
SELECT
    'azure' AS provider,
    resource_id,
    'API Management' AS service_name,
    ROUND(unit_count * hourly_price_per_unit * 730, 2) AS billed_cost,
    resource_name,
    sku,
    unit_count,
    total_requests,
    lookback_days,
    'API Management with 0 requests over ' || lookback_days || ' days (' || sku || ')' AS evidence_reason
FROM fact_idle_apim
WHERE total_requests = 0
  AND hourly_price_per_unit > 0;
