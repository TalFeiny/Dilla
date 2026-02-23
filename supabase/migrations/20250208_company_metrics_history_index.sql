-- Phase 5.2: Index for nav-timeseries queries that filter by company_id and fund_id
-- (Existing idx_company_metrics_history_fund_company_time covers fund_id, company_id, recorded_at;
--  this one supports company-first lookups when needed.)
CREATE INDEX IF NOT EXISTS idx_company_metrics_history_company_fund_time
ON company_metrics_history (company_id, fund_id, recorded_at DESC)
WHERE fund_id IS NOT NULL;
