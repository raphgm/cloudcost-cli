-- Real check: AKS node pools whose underlying VMSS runs at sustained
-- low average CPU across all nodes -- the control plane is free, so
-- this is pure node-VM waste, distinct from azure.vm_sizing which only
-- looks at standalone VMs. Price is fetched live per VM size from the
-- Retail Prices API (same live-pricing approach as vm_sizing), so this
-- check is correct for whatever node SKU the pool actually uses.
SELECT
    'azure' AS provider,
    resource_id,
    'AKS Node Pool' AS service_name,
    ROUND(node_count * hourly_price_per_node * 730, 2) AS billed_cost,
    resource_name,
    vm_size,
    node_count,
    ROUND(avg_cpu_percent, 1) AS avg_cpu_percent,
    lookback_days,
    node_count || ' x ' || vm_size || ' nodes averaging ' ||
        ROUND(avg_cpu_percent, 1) || '% CPU over ' || lookback_days || ' days' AS evidence_reason
FROM fact_aks_idle_nodepool
WHERE avg_cpu_percent < 10.0
  AND hourly_price_per_node > 0;
