-- Real check: Azure Container Instance groups with restartPolicy=Always
-- (billed per-second for requested vCPU/memory continuously) that show
-- near-zero real CPU usage over the lookback window -- a container left
-- running that nothing is calling. CpuUsage unit is millicores (Count),
-- confirmed via `az monitor metrics list-definitions`; requested_cpu is
-- in whole vCPUs (1.0 = 1000 millicores), so 5% of requested capacity
-- is the idle threshold. Prices are Azure's real, current
-- "Standard vCPU Duration" ($0.0405/hour) and "Standard Memory
-- Duration" ($0.00445/GB-hour) meters (Retail Prices API, eastus).
SELECT
    'azure' AS provider,
    resource_id,
    'Azure Container Instances' AS service_name,
    ROUND((requested_cpu * 0.0405 + requested_memory_gb * 0.00445) * 730, 2) AS billed_cost,
    resource_name,
    requested_cpu,
    requested_memory_gb,
    avg_cpu_millicores,
    lookback_days,
    'avg ' || ROUND(avg_cpu_millicores, 1) || 'm CPU vs ' || (requested_cpu * 1000) ||
        'm requested over ' || lookback_days || ' days' AS evidence_reason
FROM fact_idle_container_instances
WHERE avg_cpu_millicores < (requested_cpu * 1000 * 0.05);
