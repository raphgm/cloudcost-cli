-- Real check: Azure Managed HSM instances with zero operations over the
-- lookback window still incur a fixed per-instance fee in Standard tiers.
SELECT
    'azure' AS provider,
    resource_id,
    'Managed HSM' AS service_name,
    CASE
        WHEN sku = 'Standard_B1' THEN 10.00
        ELSE 0.00
    END AS billed_cost,
    resource_name,
    sku,
    operation_count,
    lookback_days,
    'Managed HSM with 0 operations over ' || lookback_days || ' days (' || sku || ')' AS evidence_reason
FROM fact_idle_managed_hsm
WHERE operation_count = 0;
