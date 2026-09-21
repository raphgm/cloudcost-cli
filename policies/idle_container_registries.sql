-- Real check: Standard/Premium Container Registries with 0 repositories.
-- Standard tier is $0.6666/day (real, current Retail Prices API price)
-- -- Basic tier ($0.167/day) isn't flagged since it's cheap enough that
-- an empty one isn't worth the finding.
SELECT
    'azure' AS provider,
    resource_id,
    'Container Registry' AS service_name,
    ROUND(CASE WHEN sku = 'Standard' THEN 0.6666 ELSE 1.6666 END * 30, 2) AS billed_cost,
    resource_name,
    resource_group,
    sku,
    'idle Container Registry, 0 repositories (' || sku || ' tier)' AS evidence_reason
FROM fact_idle_container_registries;
