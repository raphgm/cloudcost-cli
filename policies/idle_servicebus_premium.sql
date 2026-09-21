-- Real check: Premium-tier Service Bus namespaces with zero incoming
-- messages over the lookback window -- reserved Messaging Units billed
-- hourly regardless of traffic. $0.9275/hour per MU is Azure's real,
-- current "Premium Messaging Unit" meter (Retail Prices API, eastus).
SELECT
    'azure' AS provider,
    resource_id,
    'Service Bus Namespace (Premium)' AS service_name,
    ROUND(messaging_units * 0.9275 * 730, 2) AS billed_cost,
    resource_name,
    messaging_units,
    total_incoming_messages,
    lookback_days,
    messaging_units || ' MU reserved, zero incoming messages over ' ||
        lookback_days || ' days' AS evidence_reason
FROM fact_idle_servicebus_premium
WHERE total_incoming_messages = 0;
