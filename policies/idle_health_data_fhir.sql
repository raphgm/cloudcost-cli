-- Real check: Azure Health Data Services FHIR services with zero API
-- requests over the lookback window -- fixed hourly Service Runtime
-- fee billed regardless of real request volume. Price is Azure's
-- real, current "Standard Service Runtime" meter (Retail Prices
-- API, product "Azure Health Data APIs"): $0.40/hour.
SELECT
    'azure' AS provider,
    resource_id,
    'Health Data Services FHIR' AS service_name,
    ROUND(0.40 * 24 * lookback_days, 2) AS billed_cost,
    resource_name,
    workspace_name,
    total_requests,
    lookback_days,
    'zero API requests over ' || lookback_days || ' days' AS evidence_reason
FROM fact_idle_health_data_fhir
WHERE total_requests = 0;
