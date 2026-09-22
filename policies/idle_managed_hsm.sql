-- Real check: Azure Managed HSM pools with zero key operations over the
-- lookback window still bill the fixed hourly pool fee. The Retail
-- Prices API has no queryable meter for this product (confirmed --
-- same real gap already documented for idle_load_balancers.sql), so
-- this uses Microsoft's own published price: Standard B1 = $3.20/hour
-- (azure.microsoft.com/en-us/pricing/details/key-vault, fetched during
-- this check's verification). A prior version of this check fabricated
-- "$10.00" flat, off by roughly 240x from the real monthly cost.
SELECT
    'azure' AS provider,
    resource_id,
    'Managed HSM' AS service_name,
    ROUND(hourly_price * 730, 2) AS billed_cost,
    resource_name,
    sku,
    operation_count,
    lookback_days,
    'Managed HSM with 0 operations over ' || lookback_days || ' days (' || sku || ')' AS evidence_reason
FROM fact_idle_managed_hsm
WHERE operation_count = 0
  AND hourly_price > 0;
