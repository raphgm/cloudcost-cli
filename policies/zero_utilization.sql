SELECT
    provider,
    resource_id,
    service_name,
    billed_cost,
    'zero utilization' as evidence_reason
FROM fact_cost
WHERE
    service_name = 'Virtual Machines'
    AND billed_cost > 0
    -- In a real scenario, this would JOIN with fact_metrics
    -- For MVP, we simulate a finding
    AND provider = 'azure';
