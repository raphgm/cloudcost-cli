-- Real check: managed disks left behind after their VM was deleted or
-- resized, still billing every month with nothing attached. Standard_LRS
-- disks bill at roughly $0.045/GB/month (list price, subject to region and
-- change) — the estimate below is a rough order-of-magnitude flag, not a
-- claim of exact invoice cost.
SELECT
    'azure' AS provider,
    resource_id,
    'Managed Disk' AS service_name,
    ROUND(size_gb * 0.045, 2) AS billed_cost,
    resource_name,
    resource_group,
    size_gb,
    sku,
    'unattached managed disk, ' || size_gb || 'GB ' || sku AS evidence_reason
FROM fact_unattached_disks;
