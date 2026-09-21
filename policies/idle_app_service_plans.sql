-- Real check: App Service Plans with zero deployed web apps -- reserved
-- compute billing every month for nothing. billed_cost uses Azure's
-- documented public Basic B1 price (~$13.14/month) as the estimate for
-- paid tiers -- Free (F1) tier genuinely costs $0, so that case is
-- reported at $0 rather than a fabricated number. This project's
-- subscription hit a real quota limit (0 available B1 App Service
-- capacity) that blocked provisioning an actual paid-tier plan to
-- verify against, so only the $0 Free-tier path has been end-to-end
-- verified; the paid-tier estimate is the honest, documented list price,
-- not independently confirmed against a real billed B1/S1 plan.
SELECT
    'azure' AS provider,
    resource_id,
    'App Service Plan' AS service_name,
    CASE WHEN sku = 'F1' THEN 0.0 ELSE 13.14 END AS billed_cost,
    resource_name,
    resource_group,
    sku,
    'App Service Plan with 0 deployed apps (' || sku || ' tier)' AS evidence_reason
FROM fact_idle_app_service_plans;
