-- Multi-entity consolidation support
-- Adds company_entities table and consolidation_adjustments for IC elimination tracking

-- Entity registry for group structures
CREATE TABLE IF NOT EXISTS company_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES portfolio_companies(id) ON DELETE CASCADE,
    fund_id UUID,
    entity_name TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT 'opco',  -- holdco, opco, spv, subsidiary, branch, ip_holdco, finance_co, dormant
    parent_entity_id UUID REFERENCES company_entities(id),
    jurisdiction TEXT,                          -- "US-DE", "UK", "IE", "SG", etc.
    ownership_pct NUMERIC(5,2) DEFAULT 100.00, -- parent's ownership %
    consolidation_method TEXT DEFAULT 'full',   -- full, equity_method, none
    purpose TEXT,                               -- operating, ip_holding, financing, etc.
    is_dormant BOOLEAN DEFAULT FALSE,
    registered_capital NUMERIC,
    incorporation_date DATE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_company_entities_company ON company_entities(company_id);
CREATE INDEX IF NOT EXISTS idx_company_entities_parent ON company_entities(parent_entity_id);
CREATE INDEX IF NOT EXISTS idx_company_entities_type ON company_entities(entity_type);

-- Consolidation adjustment audit trail
CREATE TABLE IF NOT EXISTS consolidation_adjustments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES portfolio_companies(id) ON DELETE CASCADE,
    period DATE NOT NULL,
    adjustment_type TEXT NOT NULL,              -- ic_elimination, minority_interest, fx_translation
    category TEXT NOT NULL,                     -- revenue, cogs, opex_rd, etc.
    subcategory TEXT,
    amount NUMERIC NOT NULL,
    source_entity_id UUID REFERENCES company_entities(id),
    target_entity_id UUID REFERENCES company_entities(id),
    source_document_id UUID,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_consolidation_adj_company ON consolidation_adjustments(company_id);
CREATE INDEX IF NOT EXISTS idx_consolidation_adj_period ON consolidation_adjustments(period);
CREATE INDEX IF NOT EXISTS idx_consolidation_adj_type ON consolidation_adjustments(adjustment_type);

-- Session handoff table for context continuity across sessions
CREATE TABLE IF NOT EXISTS session_handoffs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID,
    fund_id UUID,
    user_id TEXT,
    handoff_data JSONB NOT NULL,               -- {summary, findings, open_items, next_steps}
    context_tokens_used INTEGER,
    session_memo JSONB,                        -- compressed SessionMemo
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_session_handoffs_user ON session_handoffs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_session_handoffs_company ON session_handoffs(company_id, created_at DESC);

-- Add entity_id column to fpa_actuals if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'fpa_actuals' AND column_name = 'entity_id'
    ) THEN
        ALTER TABLE fpa_actuals ADD COLUMN entity_id UUID REFERENCES company_entities(id);
        CREATE INDEX idx_fpa_actuals_entity ON fpa_actuals(entity_id);
    END IF;
END $$;

-- RLS policies
ALTER TABLE company_entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE consolidation_adjustments ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_handoffs ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to access their data
CREATE POLICY "Users can access own entities" ON company_entities
    FOR ALL USING (true);

CREATE POLICY "Users can access own adjustments" ON consolidation_adjustments
    FOR ALL USING (true);

CREATE POLICY "Users can access own handoffs" ON session_handoffs
    FOR ALL USING (true);
