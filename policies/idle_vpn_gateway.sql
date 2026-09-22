-- Real check: Azure VPN Gateways with zero average bandwidth over
-- the lookback window. billed_cost uses the live hourly VPN Gateway
-- price fetched by the source plugin from the Azure Retail Prices API
-- (serviceName = 'VPN Gateway', priceType = 'Consumption', exact
-- gateway SKU and region), multiplied by 730 hours/month.

SELECT
    'azure' AS provider,
    resource_id,
    'Azure VPN Gateway' AS service_name,
    ROUND(hourly_price * 730, 2) AS billed_cost,
    resource_name,
    sku,
    avg_bandwidth_bps,
    lookback_days,
    'zero average bandwidth over ' || lookback_days || ' days'
        AS evidence_reason
FROM fact_idle_vpn_gateway
WHERE avg_bandwidth_bps = 0;
