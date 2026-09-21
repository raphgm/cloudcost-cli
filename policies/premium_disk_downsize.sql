-- Real check: Premium SSD disks under 256GB where downsizing to Standard
-- SSD saves more than $5/month, using real, current Retail Prices API
-- data for both tiers -- not a hardcoded price table.
SELECT
    'azure' AS provider,
    resource_id,
    'Managed Disk' AS service_name,
    estimated_monthly_savings_usd AS billed_cost,
    resource_name,
    resource_group,
    size_gb,
    premium_price_per_month,
    standard_ssd_price_per_month,
    'Premium SSD ' || size_gb || 'GB ($' || premium_price_per_month || '/mo) could downsize to Standard SSD ($' ||
        standard_ssd_price_per_month || '/mo) for non-performance-critical workloads' AS evidence_reason
FROM fact_premium_disk_downsize;
