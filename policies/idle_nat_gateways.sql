-- Real check: NAT Gateways with no subnet attached. $0.045/hour is
-- Azure's real, current base rate for a Standard NAT Gateway (Retail
-- Prices API, serviceName='NAT Gateway', meterName='Standard Gateway',
-- pricing is global, not region-specific) -- excludes data-processing
-- charges, which are $0 at idle since nothing is routing through it.
SELECT
    'azure' AS provider,
    resource_id,
    'NAT Gateway' AS service_name,
    ROUND(0.045 * 730, 2) AS billed_cost,
    resource_name,
    resource_group,
    sku,
    'idle NAT Gateway, no subnet attached (' || sku || ' SKU)' AS evidence_reason
FROM fact_idle_nat_gateways;
