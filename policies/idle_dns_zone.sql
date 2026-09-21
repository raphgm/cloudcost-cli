-- Real check: Azure DNS zones with only the 2 default record sets
-- (SOA + NS, present in every zone even when empty) -- no real
-- A/CNAME/MX/etc records, meaning nothing resolves through this zone,
-- yet it still bills the flat monthly zone-hosting fee. $0.50/month is
-- Azure's real, current "Public Zone" meter (Retail Prices API).
SELECT
    'azure' AS provider,
    resource_id,
    'Azure DNS Zone' AS service_name,
    0.50 AS billed_cost,
    resource_name,
    record_set_count,
    'only ' || record_set_count || ' record set(s) (SOA+NS defaults), no real records configured' AS evidence_reason
FROM fact_idle_dns_zone
WHERE record_set_count <= 2;
