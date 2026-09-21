-- Real governance check: resources with no tags at all — detection only.
-- This project does not stop, delete, or otherwise remediate anything
-- automatically; it reports findings for a human (or a separate, deliberately
-- built and reviewed automation) to act on.
SELECT
    'azure' AS provider,
    resource_id,
    resource_type AS service_name,
    0.0 AS billed_cost,
    resource_name,
    resource_group,
    location,
    'untagged: ' || resource_type AS evidence_reason
FROM fact_untagged_resources;
