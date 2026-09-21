-- Real check: Standard-tier Event Hubs namespaces with zero incoming
-- messages over the lookback window -- reserved Throughput Units billed
-- hourly for a stream nobody is publishing to. $0.03/hour per TU is
-- Azure's real, current "Standard Throughput Unit" meter (Retail Prices
-- API, eastus).
SELECT
    'azure' AS provider,
    resource_id,
    'Event Hubs Namespace' AS service_name,
    ROUND(throughput_units * 0.03 * 730, 2) AS billed_cost,
    resource_name,
    throughput_units,
    total_incoming_messages,
    lookback_days,
    throughput_units || ' TU reserved, zero incoming messages over ' ||
        lookback_days || ' days' AS evidence_reason
FROM fact_idle_eventhub
WHERE total_incoming_messages = 0;
