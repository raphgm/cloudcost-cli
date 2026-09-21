-- Real check: disk snapshots older than 30 days — a standard FinOps
-- threshold (long enough that a genuine short-lived migration/rollback
-- snapshot isn't falsely flagged, short enough to catch real
-- "took it once, forgot about it" cost creep). Standard_LRS snapshot
-- pricing is roughly $0.05/GB/month (list price, region/change-dependent) --
-- a rough order-of-magnitude flag, not an exact invoice figure.
SELECT
    'azure' AS provider,
    resource_id,
    'Snapshot' AS service_name,
    ROUND(size_gb * 0.05, 2) AS billed_cost,
    resource_name,
    resource_group,
    size_gb,
    sku,
    age_days,
    'snapshot is ' || age_days || ' days old (' || size_gb || 'GB ' || sku || ')' AS evidence_reason
FROM fact_old_snapshots
WHERE age_days > 30;
