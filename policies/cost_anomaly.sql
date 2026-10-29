-- Cost anomaly detection: flags a provider/service/resource whose daily
-- spend jumps to >= 3x its own trailing 7-day average. Every other check
-- in this project finds *persistent* waste; this finds *change* -- a
-- misconfiguration or runaway process that started yesterday looks nothing
-- like steady-state waste in a cost table, so a steady-state check will
-- never catch it.
--
-- Reads from fact_cost (the normalized billing export produced by
-- azure.cost_export + focus.normalize -- see cloudcost.cost-anomaly-real.yml),
-- not from live inventory or metrics like most checks here.
WITH daily AS (
    SELECT
        provider,
        COALESCE(NULLIF(resource_id, ''), 'unknown') AS resource_id,
        service_name,
        CAST(usage_date AS DATE) AS usage_date,
        SUM(billed_cost) AS daily_cost
    FROM fact_cost
    WHERE usage_date IS NOT NULL
    GROUP BY
        provider,
        COALESCE(NULLIF(resource_id, ''), 'unknown'),
        service_name,
        CAST(usage_date AS DATE)
),
with_baseline AS (
    SELECT
        provider,
        resource_id,
        service_name,
        usage_date,
        daily_cost,
        AVG(daily_cost) OVER (
            PARTITION BY provider, resource_id, service_name
            ORDER BY usage_date
            ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
        ) AS trailing_avg_7d,
        COUNT(daily_cost) OVER (
            PARTITION BY provider, resource_id, service_name
            ORDER BY usage_date
            ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
        ) AS baseline_days
    FROM daily
)
SELECT
    provider,
    resource_id,
    service_name,
    ROUND(daily_cost, 2) AS billed_cost,
    usage_date,
    ROUND(trailing_avg_7d, 2) AS trailing_avg_7d,
    ROUND(daily_cost / trailing_avg_7d, 1) AS spike_multiplier,
    service_name || ' spend spiked to $' || ROUND(daily_cost, 2)
        || ' on ' || usage_date
        || ' vs $' || ROUND(trailing_avg_7d, 2)
        || ' trailing 7-day average ('
        || ROUND(daily_cost / trailing_avg_7d, 1) || 'x)' AS evidence_reason
FROM with_baseline
WHERE baseline_days >= 7
  AND trailing_avg_7d > 0
  AND daily_cost > 3.0 * trailing_avg_7d;
