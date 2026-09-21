-- Real check: Azure Functions Premium (Elastic Premium) plans with a
-- minimum pre-warmed instance floor and near-zero real function
-- execution volume -- the reserved instances bill hourly whether
-- functions run or not. Distinct from azure.idle_app_service_plans,
-- which only flags a plan with zero deployed apps; this one has real
-- functions deployed but low real traffic. Prices are Azure's real,
-- current "Functions Premium vCPU Duration" ($0.173/hr) and "Functions
-- Premium Memory Duration" ($0.0123/GiB-hr) meters (Retail Prices API).
SELECT
    'azure' AS provider,
    resource_id,
    'Azure Functions Premium Plan' AS service_name,
    ROUND(min_instances * hourly_price_per_instance * 730, 2) AS billed_cost,
    resource_name,
    sku,
    min_instances,
    app_count,
    total_executions,
    lookback_days,
    min_instances || ' pre-warmed ' || sku || ' instance(s), ' ||
        ROUND(total_executions, 0) || ' executions over ' || lookback_days || ' days' AS evidence_reason
FROM fact_idle_functions_premium_min_instances
WHERE total_executions < 10;
