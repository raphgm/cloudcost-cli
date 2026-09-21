-- Real utilization-based rightsizing: joins actual cost against actual
-- Azure Monitor CPU data, instead of flagging every VM with cost > 0
-- (which is what zero_utilization.sql did before this — its own comment
-- admitted "for MVP we simulate a finding"). A VM is only flagged here if
-- it is BOTH costing money AND measurably underused.
SELECT
    c.provider,
    c.resource_id,
    c.service_name,
    SUM(c.billed_cost) AS billed_cost,
    ROUND(AVG(m.avg_cpu_percent), 2) AS avg_cpu_percent,
    'sustained low CPU utilization (' || ROUND(AVG(m.avg_cpu_percent), 1) || '% avg)' AS evidence_reason
FROM fact_cost c
JOIN fact_metrics m
    ON LOWER(c.resource_id) = LOWER(m.resource_id)
WHERE
    c.service_name = 'Virtual Machines'
    AND c.billed_cost > 0
GROUP BY c.provider, c.resource_id, c.service_name
HAVING AVG(m.avg_cpu_percent) < 10.0;
