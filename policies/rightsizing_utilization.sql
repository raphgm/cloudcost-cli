-- Real multi-metric rightsizing: CPU alone can't tell an idle VM apart
-- from a lightly-loaded one that's quietly serving real network or disk
-- traffic CPU wouldn't reflect. This checks four signals and reports a
-- confidence level, rather than a single fixed threshold treated as fact.
--
-- Idle (high confidence): CPU < 5% AND negligible network AND negligible
-- disk I/O — nothing measurable is happening on any axis.
-- Underutilized (medium confidence): CPU < 20% but at least one other
-- signal is non-trivial — plausibly rightsizable, but verify before acting.
WITH metrics_agg AS (
    SELECT
        resource_id,
        AVG(avg_cpu_percent) AS avg_cpu,
        AVG(avg_network_in_bytes) AS avg_net_in,
        AVG(avg_network_out_bytes) AS avg_net_out,
        AVG(avg_disk_read_ops) AS avg_disk_read,
        AVG(avg_disk_write_ops) AS avg_disk_write
    FROM fact_metrics
    GROUP BY resource_id
)
SELECT
    c.provider,
    c.resource_id,
    c.service_name,
    SUM(c.billed_cost) AS billed_cost,
    ROUND(m.avg_cpu, 2) AS avg_cpu_percent,
    CASE
        WHEN m.avg_cpu < 5.0 AND m.avg_net_in < 50000 AND m.avg_net_out < 50000
             AND m.avg_disk_read < 5 AND m.avg_disk_write < 5
            THEN 'idle (high confidence)'
        WHEN m.avg_cpu < 20.0
            THEN 'underutilized (medium confidence — verify network/disk before resizing)'
    END AS confidence,
    'CPU ' || ROUND(m.avg_cpu, 1) || '%, net in/out ' || ROUND(m.avg_net_in, 0) || '/' || ROUND(m.avg_net_out, 0) ||
        ' bytes/s, disk r/w ' || ROUND(m.avg_disk_read, 2) || '/' || ROUND(m.avg_disk_write, 2) || ' ops/s' AS evidence_reason
FROM fact_cost c
JOIN metrics_agg m
    ON LOWER(c.resource_id) = LOWER(m.resource_id)
WHERE
    c.service_name = 'Virtual Machines'
    AND c.billed_cost > 0
    AND m.avg_cpu < 20.0
GROUP BY c.provider, c.resource_id, c.service_name, m.avg_cpu, m.avg_net_in, m.avg_net_out, m.avg_disk_read, m.avg_disk_write;
