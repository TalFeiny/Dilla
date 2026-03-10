-- Cap Table V2: Full cap table with document-derived share-level data
-- Creates company_cap_tables (original + v2 columns) and cap_table_documents join table

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
    -- V2 columns: document-derived cap table
    share_entries JSONB,
    document_ids TEXT[],
    reconciliation_log JSONB,
    model_inputs JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(portfolio_id, company_id)
);

CREATE INDEX IF NOT EXISTS idx_company_cap_tables_portfolio ON company_cap_tables(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_company_cap_tables_company ON company_cap_tables(company_id);
CREATE INDEX IF NOT EXISTS idx_company_cap_tables_updated ON company_cap_tables(updated_at DESC);

ALTER TABLE company_cap_tables ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow read company_cap_tables" ON company_cap_tables FOR SELECT USING (true);
CREATE POLICY "Allow insert company_cap_tables" ON company_cap_tables FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow update company_cap_tables" ON company_cap_tables FOR UPDATE USING (true) WITH CHECK (true);
CREATE POLICY "Allow delete company_cap_tables" ON company_cap_tables FOR DELETE USING (true);

-- Join table: which documents contributed to each cap table
CREATE TABLE IF NOT EXISTS cap_table_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cap_table_id UUID REFERENCES company_cap_tables(id) ON DELETE CASCADE,
    document_id TEXT NOT NULL,
    document_type TEXT,
    effective_date DATE,
    priority INTEGER DEFAULT 10,
    clauses_contributed JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(cap_table_id, document_id)
);

CREATE INDEX IF NOT EXISTS idx_cap_table_docs_cap_table ON cap_table_documents(cap_table_id);
CREATE INDEX IF NOT EXISTS idx_cap_table_docs_document ON cap_table_documents(document_id);
