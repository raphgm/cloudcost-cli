-- Real check: Private Endpoints with zero traffic (PEBytesIn + PEBytesOut)
-- over the lookback window -- a NIC reserving IP space and billing hourly
-- for a connection nothing uses. $0.01/hour is Azure's real, current
-- "Virtual Network Private Link Standard Private Endpoint" meter
-- (Retail Prices API).
SELECT
    'azure' AS provider,
    resource_id,
    'Private Endpoint' AS service_name,
    ROUND(0.01 * 730, 2) AS billed_cost,
    resource_name,
    total_bytes,
    lookback_days,
    'zero PEBytesIn+PEBytesOut over ' || lookback_days || ' days' AS evidence_reason
FROM fact_idle_private_endpoints
WHERE total_bytes = 0;
