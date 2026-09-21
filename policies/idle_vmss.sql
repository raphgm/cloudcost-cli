-- Real check: VMSS fixed instance count with sustained low average CPU
-- across the whole set -- the reserved capacity itself is the waste,
-- not a single VM's SKU choice. Price is fetched live per VM size from
-- the Retail Prices API (same live-pricing approach as vm_sizing and
-- aks_idle_nodepool).
SELECT
    'azure' AS provider,
    resource_id,
    'Virtual Machine Scale Set' AS service_name,
    ROUND(instance_count * hourly_price_per_instance * 730, 2) AS billed_cost,
    resource_name,
    vm_size,
    instance_count,
    ROUND(avg_cpu_percent, 1) AS avg_cpu_percent,
    lookback_days,
    instance_count || ' x ' || vm_size || ' instances averaging ' ||
        ROUND(avg_cpu_percent, 1) || '% CPU over ' || lookback_days || ' days' AS evidence_reason
FROM fact_idle_vmss
WHERE avg_cpu_percent < 10.0
  AND hourly_price_per_instance > 0;
