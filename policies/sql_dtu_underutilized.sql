-- Real check: DTU-based Azure SQL databases running under 10% average DTU
-- consumption — a genuine downsizing candidate (e.g. Standard S3 -> S0).
-- Real limitation: this only covers DTU-model databases (Basic/Standard/
-- Premium); vCore-model databases expose cpu_percent instead and aren't
-- covered by this check yet. billed_cost uses Azure's documented public
-- Basic-tier price ($4.90/month) as a placeholder impact estimate --
-- Standard/Premium tiers cost more and aren't priced here yet; this is
-- not a claim of the actual tier's real cost.
SELECT
    'azure' AS provider,
    resource_id,
    'SQL Database' AS service_name,
    4.90 AS billed_cost,
    resource_name,
    ROUND(AVG(avg_dtu_percent), 2) AS avg_dtu_percent,
    'sustained low DTU utilization (' || ROUND(AVG(avg_dtu_percent), 1) || '% avg) -- consider a lower tier' AS evidence_reason
FROM fact_sql_dtu_metrics
GROUP BY resource_id, resource_name
HAVING AVG(avg_dtu_percent) < 10.0;
