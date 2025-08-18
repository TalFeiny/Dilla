-- Data Room and Deal Management Tables for Agent City

-- Main data room table for organizing deals
CREATE TABLE IF NOT EXISTS data_rooms (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Deal Information
  deal_name TEXT NOT NULL,
  company_id INTEGER REFERENCES companies(id),
  deal_type TEXT CHECK (deal_type IN ('seed', 'series_a', 'series_b', 'series_c', 'growth', 'acquisition', 'public_market', 'hedge')),
  deal_stage TEXT CHECK (deal_stage IN ('sourcing', 'screening', 'diligence', 'negotiation', 'documentation', 'closing', 'post_close')),
  
  -- Deal Metrics
  target_investment NUMERIC,
  valuation NUMERIC,
  ownership_target NUMERIC(5,2),
  irr_target NUMERIC(5,2),
  
  -- Multi-jurisdiction Support
  primary_jurisdiction TEXT,
  secondary_jurisdictions TEXT[],
  currency_exposures JSONB, -- {USD: 0.6, EUR: 0.3, GBP: 0.1}
  
  -- Public Market Support
  ticker_symbol TEXT,
  asset_class TEXT CHECK (asset_class IN ('equity', 'debt', 'derivative', 'commodity', 'crypto', 'hybrid')),
  
  -- Access Control
  is_active BOOLEAN DEFAULT TRUE,
  access_level TEXT DEFAULT 'private',
  invited_parties TEXT[]
);

-- File storage for data room documents
CREATE TABLE IF NOT EXISTS data_room_files (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- File Information
  data_room_id INTEGER REFERENCES data_rooms(id) ON DELETE CASCADE,
  file_name TEXT NOT NULL,
  file_path TEXT NOT NULL,
  file_size INTEGER,
  mime_type TEXT,
  
  -- Document Classification
  document_type TEXT CHECK (document_type IN (
    'pitch_deck', 'financial_statements', 'cap_table', 'legal_docs',
    'dd_report', 'valuation_model', 'term_sheet', 'spa', 'sha',
    'compliance', 'tax_docs', 'ip_portfolio', 'contracts', 'other'
  )),
  
  -- File Chunks for Visualization
  chunks JSONB, -- Array of {start, end, content, relevance, highlights}
  chunk_embeddings VECTOR(1536), -- For semantic search
  
  -- Metadata
  uploaded_by TEXT,
  tags TEXT[],
  is_confidential BOOLEAN DEFAULT FALSE,
  expiry_date DATE
);

-- Deal sourcing and pipeline
CREATE TABLE IF NOT EXISTS deal_pipeline (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Deal Source
  source_type TEXT CHECK (source_type IN ('network', 'cold_outreach', 'event', 'accelerator', 'agent_sourced', 'public_market')),
  source_details TEXT,
  
  -- Company/Asset Info
  company_name TEXT NOT NULL,
  website TEXT,
  ticker TEXT, -- For public markets
  
  -- Scoring
  ai_score NUMERIC(5,2),
  hype_score NUMERIC(5,2),
  value_score NUMERIC(5,2),
  win_probability NUMERIC(5,2),
  
  -- Competition
  competing_investors TEXT[],
  our_edge TEXT,
  
  -- Status
  status TEXT CHECK (status IN ('new', 'contacted', 'meeting_scheduled', 'term_sheet_sent', 'won', 'lost', 'passed')),
  next_action TEXT,
  action_deadline DATE
);

-- Hedging and cash management
CREATE TABLE IF NOT EXISTS hedge_positions (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Position Details
  data_room_id INTEGER REFERENCES data_rooms(id),
  hedge_type TEXT CHECK (hedge_type IN ('currency', 'interest_rate', 'equity', 'commodity', 'credit')),
  instrument TEXT CHECK (instrument IN ('forward', 'future', 'option', 'swap', 'collar')),
  
  -- Position Metrics
  notional_amount NUMERIC,
  hedge_ratio NUMERIC(5,2),
  strike_price NUMERIC,
  expiry_date DATE,
  
  -- Currencies
  base_currency TEXT,
  hedge_currency TEXT,
  exchange_rate NUMERIC,
  
  -- P&L Tracking
  cost_basis NUMERIC,
  current_value NUMERIC,
  unrealized_pnl NUMERIC,
  realized_pnl NUMERIC
);

-- Cash management across jurisdictions
CREATE TABLE IF NOT EXISTS cash_positions (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Account Information
  jurisdiction TEXT NOT NULL,
  bank_name TEXT,
  account_type TEXT CHECK (account_type IN ('operating', 'investment', 'escrow', 'reserve')),
  currency TEXT NOT NULL,
  
  -- Balances
  current_balance NUMERIC,
  available_balance NUMERIC,
  pending_inflows NUMERIC,
  pending_outflows NUMERIC,
  
  -- Yield Optimization
  yield_strategy TEXT,
  current_yield NUMERIC(5,2),
  
  -- Compliance
  regulatory_restrictions TEXT[],
  repatriation_timeline INTEGER -- days
);

-- Public market positions and analysis
CREATE TABLE IF NOT EXISTS public_market_positions (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Asset Information
  ticker TEXT NOT NULL,
  exchange TEXT,
  asset_type TEXT CHECK (asset_type IN ('stock', 'etf', 'bond', 'option', 'future', 'crypto')),
  
  -- Position Details
  quantity NUMERIC,
  average_cost NUMERIC,
  current_price NUMERIC,
  market_value NUMERIC,
  
  -- Analytics from Yahoo Finance
  pe_ratio NUMERIC,
  market_cap NUMERIC,
  dividend_yield NUMERIC(5,2),
  beta NUMERIC,
  
  -- AI Analysis
  ai_rating TEXT CHECK (ai_rating IN ('strong_buy', 'buy', 'hold', 'sell', 'strong_sell')),
  alpha_opportunity BOOLEAN DEFAULT FALSE,
  correlation_to_portfolio NUMERIC(5,2),
  
  -- Risk Metrics
  var_95 NUMERIC, -- Value at Risk
  sharpe_ratio NUMERIC,
  max_drawdown NUMERIC(5,2)
);

-- Deal winning strategies
CREATE TABLE IF NOT EXISTS deal_strategies (
  id SERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  -- Deal Reference
  deal_pipeline_id INTEGER REFERENCES deal_pipeline(id),
  
  -- Winning Strategy
  strategy_type TEXT CHECK (strategy_type IN ('price', 'speed', 'value_add', 'relationship', 'structure')),
  
  -- Our Differentiators
  unique_value_props JSONB,
  key_relationships TEXT[],
  
  -- Competitive Intelligence
  competitor_weaknesses JSONB,
  our_advantages JSONB,
  
  -- Execution Plan
  action_items JSONB,
  timeline JSONB,
  success_probability NUMERIC(5,2)
);

-- File chunk search index
CREATE TABLE IF NOT EXISTS file_chunks (
  id SERIAL PRIMARY KEY,
  file_id INTEGER REFERENCES data_room_files(id) ON DELETE CASCADE,
  
  -- Chunk Information
  chunk_index INTEGER,
  content TEXT,
  start_position INTEGER,
  end_position INTEGER,
  
  -- Semantic Search
  embedding VECTOR(1536),
  
  -- Relevance Scoring
  importance_score NUMERIC(5,2),
  keywords TEXT[],
  entities JSONB -- Named entities extracted
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_data_rooms_company ON data_rooms(company_id);
CREATE INDEX IF NOT EXISTS idx_data_rooms_stage ON data_rooms(deal_stage);
CREATE INDEX IF NOT EXISTS idx_data_room_files_room ON data_room_files(data_room_id);
CREATE INDEX IF NOT EXISTS idx_data_room_files_type ON data_room_files(document_type);
CREATE INDEX IF NOT EXISTS idx_deal_pipeline_status ON deal_pipeline(status);
CREATE INDEX IF NOT EXISTS idx_deal_pipeline_score ON deal_pipeline(ai_score DESC);
CREATE INDEX IF NOT EXISTS idx_hedge_positions_room ON hedge_positions(data_room_id);
CREATE INDEX IF NOT EXISTS idx_public_positions_ticker ON public_market_positions(ticker);
CREATE INDEX IF NOT EXISTS idx_file_chunks_file ON file_chunks(file_id);

-- Vector similarity search index (requires pgvector extension)
-- CREATE INDEX IF NOT EXISTS idx_file_chunks_embedding ON file_chunks USING ivfflat (embedding vector_cosine_ops);

-- Row Level Security
ALTER TABLE data_rooms ENABLE ROW LEVEL SECURITY;
ALTER TABLE data_room_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE deal_pipeline ENABLE ROW LEVEL SECURITY;
ALTER TABLE hedge_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE cash_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public_market_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE deal_strategies ENABLE ROW LEVEL SECURITY;
ALTER TABLE file_chunks ENABLE ROW LEVEL SECURITY;

-- Policies
CREATE POLICY "Enable read access for all users" ON data_rooms FOR SELECT USING (true);
CREATE POLICY "Enable insert for authenticated users" ON data_rooms FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable update for authenticated users" ON data_rooms FOR UPDATE USING (true);

CREATE POLICY "Enable read access for all users" ON data_room_files FOR SELECT USING (true);
CREATE POLICY "Enable insert for authenticated users" ON data_room_files FOR INSERT WITH CHECK (true);

CREATE POLICY "Enable read access for all users" ON deal_pipeline FOR SELECT USING (true);
CREATE POLICY "Enable insert for authenticated users" ON deal_pipeline FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable update for authenticated users" ON deal_pipeline FOR UPDATE USING (true);

CREATE POLICY "Enable read access for all users" ON public_market_positions FOR SELECT USING (true);
CREATE POLICY "Enable insert for authenticated users" ON public_market_positions FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable update for authenticated users" ON public_market_positions FOR UPDATE USING (true);