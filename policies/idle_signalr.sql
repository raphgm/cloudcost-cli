-- Real check: Azure SignalR Service Standard/Premium instances with
-- zero connections over the lookback window -- fixed units billed
-- per-day whether anything connects or not. Prices are Azure's real,
-- current "<Tier> Unit" meters (Retail Prices API, eastus):
-- Standard $1.61/day/unit, Premium $2.00/day/unit.
SELECT
    'azure' AS provider,
    resource_id,
    'Azure SignalR Service' AS service_name,
    ROUND(
        unit_count * (CASE WHEN sku LIKE '%Premium%' THEN 2.00 ELSE 1.61 END) * 30,
        2
    ) AS billed_cost,
    resource_name,
    sku,
    unit_count,
    total_connections,
    lookback_days,
    unit_count || ' unit(s) reserved, zero connections over ' ||
        lookback_days || ' days' AS evidence_reason
FROM fact_idle_signalr
WHERE total_connections = 0;
