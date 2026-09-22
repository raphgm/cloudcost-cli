-- Real check: Azure ML Compute Clusters (AmlCompute) with a nonzero
-- minimum node count -- these training clusters are designed to scale
-- to zero between jobs, so min_instances should almost always be 0.
-- A nonzero minimum keeps that many nodes always-warm, billed at the
-- standard VM-hour rate continuously, regardless of whether a real
-- training job is queued. Price fetched live per real VM size via
-- the Retail Prices API.
SELECT
    'azure' AS provider,
    resource_id,
    'Azure ML Compute Cluster' AS service_name,
    ROUND(min_instances * hourly_price_per_node * 730, 2) AS billed_cost,
    resource_name,
    vm_size,
    min_instances,
    min_instances || ' always-warm ' || vm_size || ' node(s) (should be 0 for a training cluster)' AS evidence_reason
FROM fact_idle_aml_compute_cluster
WHERE hourly_price_per_node > 0;
