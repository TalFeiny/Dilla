-- Company Cap Tables: persisted cap table calculations so they survive sessions.
-- Keyed on (portfolio_id, company_id) — one cap table per company per portfolio.

CREATE TABLE IF NOT EXISTS company_cap_tables (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id UUID NOT NULL,
    company_id UUID NOT NULL,
    company_name TEXT NOT NULL DEFAULT '',
    cap_table_json JSONB NOT NULL DEFAULT '{}',
    sankey_data JSONB,
    waterfall_data JSONB,
    ownership_summary JSONB,
    founder_ownership NUMERIC,
    total_raised NUMERIC,
    num_rounds INTEGER,
    source TEXT NOT NULL DEFAULT 'synthetic' CHECK (source IN ('extracted', 'synthetic', 'hybrid')),
    funding_data_source TEXT,
    confidence NUMERIC,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(portfolio_id, company_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_company_cap_tables_portfolio ON company_cap_tables(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_company_cap_tables_company ON company_cap_tables(company_id);
CREATE INDEX IF NOT EXISTS idx_company_cap_tables_updated ON company_cap_tables(updated_at DESC);

-- RLS
ALTER TABLE company_cap_tables ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow read company_cap_tables" ON company_cap_tables FOR SELECT USING (true);
CREATE POLICY "Allow insert company_cap_tables" ON company_cap_tables FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow update company_cap_tables" ON company_cap_tables FOR UPDATE USING (true) WITH CHECK (true);
CREATE POLICY "Allow delete company_cap_tables" ON company_cap_tables FOR DELETE USING (true);

COMMENT ON TABLE company_cap_tables IS 'Persisted cap table calculations per company per portfolio. Survives sessions and avoids re-computation.';
