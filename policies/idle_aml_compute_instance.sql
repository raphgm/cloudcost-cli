-- Real check: Azure Machine Learning Compute Instances left Running
-- with no idle-shutdown safety net configured -- these bill
-- continuously at the standard VM-hour rate for the instance's size,
-- and AML's idle-shutdown feature is opt-in, not default. Price
-- fetched live per real VM size via the Retail Prices API.
SELECT
    'azure' AS provider,
    resource_id,
    'Azure ML Compute Instance' AS service_name,
    ROUND(hourly_price * 730, 2) AS billed_cost,
    resource_name,
    vm_size,
    state,
    'Running with no idle-shutdown configured (' || vm_size || ')' AS evidence_reason
FROM fact_idle_aml_compute_instance
WHERE hourly_price > 0;
