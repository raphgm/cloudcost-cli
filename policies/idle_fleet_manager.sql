-- Real check: Azure Kubernetes Fleet Manager hubs bill a fixed monthly fee
-- when enabled, even when no member clusters are attached or no update runs
-- are happening across the lookback window.
SELECT
    'azure' AS provider,
    resource_id,
    'Fleet Manager' AS service_name,
    CASE
        WHEN sku = 'Standard' THEN 30.00
        ELSE 0.00
    END AS billed_cost,
    resource_name,
    sku,
    member_cluster_count,
    update_runs,
    lookback_days,
    'Fleet Manager with 0 member clusters over ' || lookback_days || ' days (' || sku || ')' AS evidence_reason
FROM fact_idle_fleet_manager
WHERE member_cluster_count = 0;
