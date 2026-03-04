-- Transfer Pricing: multi-entity data model, intercompany transactions, FAR profiles,
-- entity financials, comparable search results, TP analyses, and compliance documents.

-- ============================================================================
-- PHASE 0: Multi-Entity Data Model
-- ============================================================================

-- Company group — portfolio company IS the group (company_id is the parent)
CREATE TABLE IF NOT EXISTS company_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,  -- parent portfolio company = the group
    name TEXT NOT NULL,                           -- "Acme UK Ltd"
    jurisdiction TEXT NOT NULL,                   -- ISO 3166-1 alpha-2: "GB", "IE", "US"
    entity_type TEXT NOT NULL,                    -- "operating", "ip_holding", "distribution", "services", "financing", "dormant"
    functional_role TEXT,                         -- free text summary, AI-generated
    local_currency TEXT NOT NULL DEFAULT 'USD',   -- "GBP", "EUR", "USD"
    tax_id TEXT,                                  -- local tax registration number
    incorporation_date DATE,
    is_tested_party BOOLEAN DEFAULT false,        -- flag commonly tested entities
    xero_tenant_id TEXT,                          -- link to Xero connection if applicable
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_company_entities_company ON company_entities(company_id);

-- Structured Functions / Assets / Risks per entity (FAR profiles)
CREATE TABLE IF NOT EXISTS entity_far_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL REFERENCES company_entities(id) ON DELETE CASCADE,
    functions JSONB NOT NULL DEFAULT '[]',         -- [{"function": "r_and_d", "significance": "high", "description": "..."}]
    assets JSONB NOT NULL DEFAULT '[]',            -- [{"asset": "patents", "type": "intangible", "significance": "high"}]
    risks JSONB NOT NULL DEFAULT '[]',             -- [{"risk": "market_risk", "significance": "medium", "description": "..."}]
    narrative TEXT,                                -- AI-generated summary
    source TEXT NOT NULL DEFAULT 'manual',         -- "manual", "ai_inferred", "xero_derived"
    confidence FLOAT DEFAULT 0.5,
    last_reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_far_one_per_entity ON entity_far_profiles(entity_id);

-- Intercompany transactions
CREATE TABLE IF NOT EXISTS intercompany_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,  -- parent group
    from_entity_id UUID NOT NULL REFERENCES company_entities(id),
    to_entity_id UUID NOT NULL REFERENCES company_entities(id),
    transaction_type TEXT NOT NULL,                -- "services", "ip_licensing", "goods", "financing", "cost_sharing"
    description TEXT NOT NULL,
    annual_value NUMERIC,
    currency TEXT NOT NULL DEFAULT 'USD',
    pricing_method_current TEXT,                   -- "cost_plus_10pct", "5pct_royalty", "fixed_fee", "unknown"
    pricing_basis TEXT,                            -- "cost_plus", "percentage_of_revenue", "fixed_fee", "unit_price"
    period_start DATE,
    period_end DATE,                               -- null = ongoing
    last_benchmarked_at TIMESTAMPTZ,
    benchmark_status TEXT DEFAULT 'not_assessed',  -- "not_assessed", "in_range", "out_of_range", "needs_review"
    source TEXT NOT NULL DEFAULT 'manual',          -- "manual", "xero_detected", "document_extracted"
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    CHECK (from_entity_id != to_entity_id)
);

CREATE INDEX IF NOT EXISTS idx_ic_txns_company ON intercompany_transactions(company_id);
CREATE INDEX IF NOT EXISTS idx_ic_txns_entities ON intercompany_transactions(from_entity_id, to_entity_id);

-- Entity-level financials
CREATE TABLE IF NOT EXISTS entity_financials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL REFERENCES company_entities(id) ON DELETE CASCADE,
    period DATE NOT NULL,                          -- 1st of month
    category TEXT NOT NULL,                        -- "revenue", "cogs", "opex", "operating_profit", "gross_profit", "total_assets", "headcount"
    subcategory TEXT,                              -- "third_party_revenue", "intercompany_revenue", "r&d_costs", etc.
    amount NUMERIC NOT NULL,
    currency TEXT NOT NULL,
    amount_group_currency NUMERIC,                 -- converted to parent company base currency
    fx_rate_used NUMERIC,
    source TEXT NOT NULL DEFAULT 'manual',          -- "manual", "xero", "csv_upload", "document_extracted"
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_entity_fin_entity_period ON entity_financials(entity_id, period, category);
CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_fin_dedup ON entity_financials(entity_id, period, category, COALESCE(subcategory, ''), source);

-- ============================================================================
-- PHASE 2: IC Transaction Suggestions (from Xero / doc detection)
-- ============================================================================

CREATE TABLE IF NOT EXISTS ic_transaction_suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    from_entity_id UUID REFERENCES company_entities(id),
    to_entity_id UUID REFERENCES company_entities(id),
    transaction_type TEXT,
    description TEXT NOT NULL,
    annual_value NUMERIC,
    currency TEXT,
    source TEXT NOT NULL,                           -- "xero_detected", "document_extracted"
    source_detail JSONB,                            -- xero account codes, document IDs, etc.
    status TEXT NOT NULL DEFAULT 'pending',         -- "pending", "accepted", "rejected"
    accepted_transaction_id UUID REFERENCES intercompany_transactions(id),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ic_suggestions_company ON ic_transaction_suggestions(company_id, status);

-- ============================================================================
-- PHASE 3: Comparable Search Results
-- ============================================================================

CREATE TABLE IF NOT EXISTS tp_comparable_searches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES intercompany_transactions(id) ON DELETE CASCADE,
    tested_party_entity_id UUID NOT NULL REFERENCES company_entities(id),
    search_params JSONB NOT NULL,                   -- regions, SIC codes, revenue range, etc.
    status TEXT NOT NULL DEFAULT 'running',          -- "running", "completed", "failed"
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS tp_comparables (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    search_id UUID NOT NULL REFERENCES tp_comparable_searches(id) ON DELETE CASCADE,
    candidate_name TEXT NOT NULL,
    candidate_source TEXT NOT NULL,                  -- "portfolio", "yfinance", "web_search"
    candidate_source_id TEXT,                        -- portfolio company_id, ticker, URL
    -- OECD 5-factor scores (0-10)
    score_product_service SMALLINT,
    score_functional SMALLINT,
    score_contractual SMALLINT,
    score_economic SMALLINT,
    score_business_strategy SMALLINT,
    composite_score FLOAT,
    -- Status
    accepted BOOLEAN NOT NULL DEFAULT true,
    rejection_reason TEXT,                           -- required if not accepted
    -- Extracted financials
    financials JSONB,                               -- {operating_margin, gross_margin, berry_ratio, markup, revenue, ...}
    financial_years JSONB,                           -- ["2023", "2024", "2025"]
    data_quality TEXT DEFAULT 'estimated',           -- "audited", "unaudited", "estimated"
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tp_comparables_search ON tp_comparables(search_id);

-- ============================================================================
-- PHASE 4: TP Analysis Results
-- ============================================================================

CREATE TABLE IF NOT EXISTS tp_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES intercompany_transactions(id) ON DELETE CASCADE,
    search_id UUID REFERENCES tp_comparable_searches(id),
    method TEXT NOT NULL,                            -- "cup", "tnmm", "cost_plus", "resale_price", "profit_split"
    method_reasoning TEXT,
    profit_level_indicator TEXT,                     -- "operating_margin", "berry_ratio", "markup_on_total_costs", etc.
    -- Results
    tested_party_pli FLOAT,
    tested_party_pli_by_year JSONB,                 -- {"2023": 5.2, "2024": 6.1}
    comparable_results JSONB,                       -- per-comparable PLI data
    iqr_low FLOAT,
    iqr_high FLOAT,
    median FLOAT,
    full_range_low FLOAT,
    full_range_high FLOAT,
    in_range BOOLEAN,
    adjustment_needed FLOAT,
    adjustment_direction TEXT,                       -- "increase_price", "decrease_price"
    -- Alternative methods considered
    alternative_methods JSONB,                      -- [{method, applicable, reasoning}]
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tp_analyses_txn ON tp_analyses(transaction_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tp_analyses_latest ON tp_analyses(transaction_id, method);

-- ============================================================================
-- PHASE 5: TP Reports & Compliance Documents
-- ============================================================================

CREATE TABLE IF NOT EXISTS tp_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    report_type TEXT NOT NULL,                       -- "benchmark", "local_file", "master_file", "cbcr", "full_pack"
    entity_id UUID REFERENCES company_entities(id), -- for local files
    fiscal_year TEXT NOT NULL,                       -- "2025"
    title TEXT NOT NULL,
    content JSONB,                                  -- structured report content
    pdf_url TEXT,                                   -- storage URL after export
    pptx_url TEXT,
    status TEXT NOT NULL DEFAULT 'draft',            -- "draft", "final", "archived"
    generated_by TEXT DEFAULT 'ai',                  -- "ai", "manual"
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tp_reports_company ON tp_reports(company_id, fiscal_year);

-- ============================================================================
-- PHASE 6: FX Rate History (for currency normalization)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fx_rates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    base_currency TEXT NOT NULL DEFAULT 'USD',
    target_currency TEXT NOT NULL,
    rate NUMERIC NOT NULL CHECK (rate > 0),
    rate_date DATE NOT NULL,
    rate_type TEXT NOT NULL DEFAULT 'daily',         -- "daily", "monthly_avg", "annual_avg"
    source TEXT NOT NULL DEFAULT 'ecb',              -- "ecb", "exchangerate_host", "manual"
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_fx_rates_dedup ON fx_rates(base_currency, target_currency, rate_date, rate_type);
CREATE INDEX IF NOT EXISTS idx_fx_rates_lookup ON fx_rates(base_currency, target_currency, rate_date);
