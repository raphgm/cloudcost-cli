-- Real check: Premium Container Registries with geo-replicas -- each
-- replica region bills the full Premium tier rate ($1.6666/day, real,
-- current Retail Prices API price, same rate used in
-- idle_container_registries.sql), on top of the primary region's own
-- Premium charge. A registry can't tell you whether a replica region
-- is actually being pulled from (ACR doesn't expose per-replica pull
-- metrics), so this reports the real recurring cost of every extra
-- replica as a "review whether this region is needed" flag.
SELECT
    'azure' AS provider,
    resource_id,
    'Container Registry (geo-replica)' AS service_name,
    ROUND(extra_replica_count * 1.6666 * 30, 2) AS billed_cost,
    resource_name,
    primary_location,
    extra_replica_count,
    extra_replica_count || ' extra geo-replica region(s) beyond primary (' ||
        primary_location || ')' AS evidence_reason
FROM fact_idle_acr_geo_replication;
