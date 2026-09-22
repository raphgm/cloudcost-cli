-- Real check: Azure OpenAI deployments on a Provisioned Throughput
-- (PTU) SKU with zero real tokens processed over the lookback window --
-- reserved capacity billed hourly regardless of token volume.
-- Standard/GlobalStandard deployments are pay-per-token and have no
-- equivalent waste (idle usage already costs $0), so only Provisioned
-- SKUs are checked. Prices are Azure's real, current per-unit-hour
-- meters (Retail Prices API, 'Azure OpenAI' service, eastus):
-- GlobalProvisionedManaged = $1.00/hr, ProvisionedManaged (regional)
-- = $2.00/hr, DataZoneProvisionedManaged = $1.10/hr.
SELECT
    'azure' AS provider,
    resource_id,
    'Azure OpenAI (Provisioned Throughput)' AS service_name,
    ROUND(
        ptu_capacity * (
            CASE sku
                WHEN 'GlobalProvisionedManaged' THEN 1.00
                WHEN 'DataZoneProvisionedManaged' THEN 1.10
                ELSE 2.00
            END
        ) * 730,
        2
    ) AS billed_cost,
    resource_name,
    model,
    sku,
    ptu_capacity,
    total_tokens,
    lookback_days,
    ptu_capacity || ' PTU (' || sku || ') reserved for ' || model ||
        ', zero tokens processed over ' || lookback_days || ' days' AS evidence_reason
FROM fact_idle_openai_ptu
WHERE total_tokens = 0;
