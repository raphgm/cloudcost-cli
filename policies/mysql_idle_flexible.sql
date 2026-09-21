-- Real check: Azure Database for MySQL Flexible Server instances with
-- sustained low CPU -- the provisioned compute tier bills hourly
-- regardless of connections or query load. Price fetched live per SKU
-- via the Retail Prices API.
SELECT
    'azure' AS provider,
    resource_id,
    'Azure Database for MySQL' AS service_name,
    ROUND(hourly_price * 730, 2) AS billed_cost,
    resource_name,
    sku_name,
    ROUND(avg_cpu_percent, 1) AS avg_cpu_percent,
    lookback_days,
    sku_name || ' averaging ' || ROUND(avg_cpu_percent, 1) || '% CPU over ' ||
        lookback_days || ' days' AS evidence_reason
FROM fact_mysql_idle_flexible
WHERE avg_cpu_percent < 5.0
  AND hourly_price > 0;
