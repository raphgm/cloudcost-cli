-- Live SKU-downsize recommendation: real current Azure VM SKU capabilities
-- (az vm list-skus) joined against real, current pricing (Azure Retail
-- Prices API, prices.azure.com — no auth needed). Deliberately not a
-- hardcoded SKU-to-price lookup table: those go stale the moment Azure
-- changes a price or ships a new SKU family, and there's no way to tell
-- from the code alone that it has.
SELECT
    'azure' AS provider,
    resource_id,
    'Virtual Machines' AS service_name,
    estimated_monthly_savings_usd AS billed_cost,
    resource_name,
    current_size,
    current_price_per_hour,
    recommended_size,
    recommended_price_per_hour,
    'downsize ' || current_size || ' -> ' || recommended_size ||
        ' (live price: $' || current_price_per_hour || '/hr -> $' || recommended_price_per_hour || '/hr)' AS evidence_reason
FROM fact_vm_sizing_recommendation
WHERE estimated_monthly_savings_usd > 0;
