-- Real check: Logic Apps Standard (WorkflowStandard) plans with a real
-- Logic App deployed but near-zero real workflow runs -- the reserved
-- vCPU/memory bills hourly regardless of run activity. Prices are
-- Azure's real, current "Standard vCPU Duration" ($0.1997/hr) and
-- "Standard Memory Duration" ($0.0143/GiB-hr) meters (Retail Prices
-- API, 'Logic Apps' service).
SELECT
    'azure' AS provider,
    resource_id,
    'Logic Apps Standard Plan' AS service_name,
    ROUND(hourly_price * 730, 2) AS billed_cost,
    resource_name,
    sku,
    capacity,
    app_count,
    total_runs,
    lookback_days,
    sku || ' plan (' || capacity || ' instance(s)), ' || app_count ||
        ' app(s), ' || ROUND(total_runs, 0) || ' runs over ' || lookback_days || ' days' AS evidence_reason
FROM fact_idle_logic_apps_standard
WHERE total_runs < 5;
