-- Real check: Container Apps Environments with a Dedicated workload
-- profile and zero container apps deployed -- reserved node capacity
-- billed hourly whether anything runs on it or not. Prices are
-- Azure's real, current "Dedicated Plan Management" ($0.10/hour) and
-- "Dedicated vCPU Usage" ($0.057077/hour) meters (Retail Prices API,
-- 'Azure Container Apps' service, eastus). D4 profile = 4 vCPUs.
SELECT
    'azure' AS provider,
    resource_id,
    'Container Apps Dedicated Plan' AS service_name,
    ROUND((0.10 + min_nodes * 4 * 0.057077) * 730, 2) AS billed_cost,
    resource_name,
    workload_profile_type,
    min_nodes,
    app_count,
    'Dedicated profile (' || workload_profile_type || ') with ' || app_count ||
        ' container apps deployed' AS evidence_reason
FROM fact_idle_container_apps_dedicated
WHERE app_count = 0;
