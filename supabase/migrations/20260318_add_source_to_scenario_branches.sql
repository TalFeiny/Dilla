-- Add source column to scenario_branches for provenance tracking.
-- Tracks what created the branch: forecast_projection, monte_carlo,
-- sensitivity, valuation, metrics_snapshot, budget_variance, etc.

ALTER TABLE scenario_branches
  ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_scenario_branches_source
  ON scenario_branches (company_id, source)
  WHERE source != '';
