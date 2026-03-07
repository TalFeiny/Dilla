-- Forecast Persistence Layer
-- Saves every forecast the agent produces with full provenance.

-- Forecast header: one row per forecast run
CREATE TABLE IF NOT EXISTS fpa_forecasts (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  company_id text NOT NULL,
  fund_id text DEFAULT NULL,
  name text NOT NULL DEFAULT 'Untitled Forecast',

  -- Method provenance
  method text NOT NULL DEFAULT 'growth_rate',
    -- 'growth_rate' | 'regression' | 'driver_based' | 'seasonal'
    -- | 'budget_pct' | 'manual' | 'scenario_promoted'
  basis text NOT NULL DEFAULT 'actuals',
    -- 'actuals' | 'budget' | 'scenario' | 'manual' | 'hybrid'

  -- Full snapshot of inputs that produced this forecast
  seed_snapshot jsonb NOT NULL DEFAULT '{}',
  assumptions jsonb NOT NULL DEFAULT '{}',

  -- Lifecycle
  status text NOT NULL DEFAULT 'draft',
    -- 'draft' | 'active' | 'approved' | 'archived'
  is_active boolean NOT NULL DEFAULT false,

  horizon_months int NOT NULL DEFAULT 24,
  granularity text NOT NULL DEFAULT 'monthly',
  start_period text NOT NULL,  -- 'YYYY-MM'

  -- Audit
  created_by text DEFAULT 'agent',
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),

  -- Explainability
  explanation text DEFAULT NULL
);

-- Only one active forecast per company
CREATE UNIQUE INDEX IF NOT EXISTS idx_fpa_forecasts_one_active
  ON fpa_forecasts (company_id) WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_fpa_forecasts_company
  ON fpa_forecasts (company_id, created_at DESC);


-- Forecast line items: one row per (period, category)
CREATE TABLE IF NOT EXISTS fpa_forecast_lines (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  forecast_id uuid NOT NULL REFERENCES fpa_forecasts(id) ON DELETE CASCADE,
  period text NOT NULL,            -- 'YYYY-MM-01'
  category text NOT NULL,          -- 'revenue', 'cogs', 'opex_rd', etc.
  subcategory text NOT NULL DEFAULT '',
  hierarchy_path text NOT NULL DEFAULT '',
  amount float NOT NULL,

  -- Per-cell explainability
  derivation text DEFAULT NULL,
  source_driver text DEFAULT NULL,

  UNIQUE (forecast_id, period, category, subcategory, hierarchy_path)
);

CREATE INDEX IF NOT EXISTS idx_fpa_forecast_lines_lookup
  ON fpa_forecast_lines (forecast_id, period);


-- Audit log for forecast lifecycle events
CREATE TABLE IF NOT EXISTS fpa_forecast_audit (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  company_id text NOT NULL,
  forecast_id uuid REFERENCES fpa_forecasts(id) ON DELETE SET NULL,
  action text NOT NULL,
    -- 'created' | 'activated' | 'archived' | 'promoted_from_scenario'
    -- | 'applied_to_grid' | 'cell_edited' | 'driver_changed'
  actor text NOT NULL DEFAULT 'agent',
  details jsonb DEFAULT '{}',
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fpa_forecast_audit_company
  ON fpa_forecast_audit (company_id, created_at DESC);
