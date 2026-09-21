-- Real check: unattached Premium SSD v2 / Ultra disks provisioned
-- above the free IOPS/throughput baseline (3000 IOPS / 125 MBps) --
-- these are billed as separate dimensions from capacity and keep
-- billing whether the disk is attached to anything or not. Prices are
-- Azure's real, current "Premium LRS Provisioned IOPS" ($0.000007/hr)
-- and "Premium LRS Provisioned Throughput (MBps)" ($0.000055/hr)
-- meters (Retail Prices API, 'Azure Premium SSD v2' product, eastus).
SELECT
    'azure' AS provider,
    resource_id,
    'Premium SSD v2 (unattached)' AS service_name,
    ROUND((overage_iops * 0.000007 + overage_mbps * 0.000055) * 730, 2) AS billed_cost,
    resource_name,
    sku,
    overage_iops,
    overage_mbps,
    overage_iops || ' IOPS + ' || overage_mbps || ' MBps above free baseline, disk unattached' AS evidence_reason
FROM fact_idle_premiumv2_disk_overage;
