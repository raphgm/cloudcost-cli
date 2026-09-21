-- Real check: Log Analytics workspaces on a Commitment Tier (Capacity
-- Reservation) that ingest under 20% of the reserved GB/day over the
-- lookback window -- paying the fixed daily rate for headroom nobody
-- uses. Daily prices are Azure's real, current "Azure Monitor <N> GB
-- Commitment Tier Capacity Reservation" meters (Retail Prices API,
-- eastus): 100GB=$196/day, 1000GB=$1700/day, 10000GB=$15640/day.
SELECT
    'azure' AS provider,
    resource_id,
    'Log Analytics Workspace' AS service_name,
    ROUND(
        CASE reserved_gb_per_day
            WHEN 1000 THEN 1700.0
            WHEN 10000 THEN 15640.0
            ELSE 196.0
        END * 30, 2
    ) AS billed_cost,
    resource_name,
    reserved_gb_per_day,
    ROUND(total_gb_ingested / lookback_days, 2) AS avg_gb_ingested_per_day,
    lookback_days,
    reserved_gb_per_day || ' GB/day reserved, only ' ||
        ROUND(total_gb_ingested / lookback_days, 2) || ' GB/day avg ingested' AS evidence_reason
FROM fact_log_analytics_idle_commitment
WHERE (total_gb_ingested / lookback_days) < (reserved_gb_per_day * 0.2);
