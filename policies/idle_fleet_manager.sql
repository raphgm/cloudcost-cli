-- Real check: Azure Kubernetes Fleet Manager itself is free -- Microsoft's
-- official pricing page states "Azure Kubernetes Fleet Manager resource
-- is free to use," confirmed live during this check's verification. The
-- real cost is the hub cluster's own AKS infrastructure (a real
-- Standard_DS3_v2 node by default), which bills continuously whether
-- any member clusters are attached or not. Price fetched live via the
-- Retail Prices API for the hub's real VM size.
SELECT
    'azure' AS provider,
    resource_id,
    'AKS Fleet Manager (hub infrastructure)' AS service_name,
    ROUND(hourly_price * 730, 2) AS billed_cost,
    resource_name,
    hub_vm_size,
    member_cluster_count,
    'Fleet hub with 0 member clusters attached (' || hub_vm_size || ' node)' AS evidence_reason
FROM fact_idle_fleet_manager
WHERE member_cluster_count = 0
  AND hourly_price > 0;
