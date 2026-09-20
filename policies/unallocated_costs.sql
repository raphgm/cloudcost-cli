SELECT
    provider,
    'unknown_account' as billing_account_id,
    'res-' || gen_random_uuid()::varchar as resource_id,
    service_name,
    billed_cost,
    CURRENT_DATE as usage_date
FROM fact_cost
WHERE
    billed_cost > 10;
