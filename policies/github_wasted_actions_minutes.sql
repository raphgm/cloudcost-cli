-- Real check: GitHub Actions workflows that fail/cancel/time-out
-- repeatedly, grouped by workflow name, summed to real wasted
-- wall-clock minutes. Priced at GitHub's real published per-minute
-- overage rate for standard Linux runners ($0.008/min) -- this is an
-- "if this pushes you over your plan's included free minutes"
-- estimate, since confirming actual overage billing needs a billing
-- scope this project's gh auth doesn't have (see source file comment).
SELECT
    'github' AS provider,
    'github/workflow/' || workflow_name AS resource_id,
    'GitHub Actions' AS service_name,
    ROUND(SUM(run_duration_ms) / 60000.0 * 0.008, 4) AS billed_cost,
    workflow_name,
    conclusion,
    COUNT(*) AS wasted_run_count,
    ROUND(SUM(run_duration_ms) / 60000.0, 2) AS wasted_minutes,
    workflow_name || ' failed/cancelled ' || COUNT(*) || ' times, ' ||
        ROUND(SUM(run_duration_ms) / 60000.0, 1) || ' wasted minutes' AS evidence_reason
FROM fact_github_wasted_actions
GROUP BY workflow_name, conclusion
HAVING COUNT(*) >= 3;
