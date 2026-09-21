-- Real check: Azure Batch pools with dedicated nodes allocated and
-- zero active jobs right now -- the reserved VM capacity bills the
-- same per-hour rate as a standalone VM whether real tasks run on it
-- or not. Price fetched live per VM size via the Retail Prices API.
SELECT
    'azure' AS provider,
    resource_id,
    'Azure Batch Pool' AS service_name,
    ROUND(dedicated_nodes * hourly_price_per_node * 730, 2) AS billed_cost,
    resource_name,
    vm_size,
    dedicated_nodes,
    active_job_count,
    dedicated_nodes || ' x ' || vm_size || ' dedicated node(s), ' ||
        active_job_count || ' active jobs' AS evidence_reason
FROM fact_idle_batch_pool
WHERE active_job_count = 0
  AND hourly_price_per_node > 0;
