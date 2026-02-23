-- LP-Fund many-to-many join table
-- An LP can commit to multiple funds; a fund has many LPs.
-- Replaces the 1:1 fund_id column on limited_partners.
-- Stores per-commitment capital account, side letters, fee terms.

CREATE TABLE IF NOT EXISTS lp_fund_commitments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Foreign keys
  lp_id UUID NOT NULL REFERENCES limited_partners(id) ON DELETE CASCADE,
  fund_id UUID NOT NULL,

  -- Capital account
  commitment_usd NUMERIC NOT NULL DEFAULT 0,
  called_usd NUMERIC NOT NULL DEFAULT 0,
  distributed_usd NUMERIC NOT NULL DEFAULT 0,
  recallable_usd NUMERIC NOT NULL DEFAULT 0,

  -- Ownership / allocation
  ownership_pct NUMERIC DEFAULT 0,        -- LP's % of total fund commitments
  vintage_year INTEGER,

  -- Fee & carry terms (per-commitment, may differ from fund default)
  management_fee_pct NUMERIC DEFAULT 2.0,
  carried_interest_pct NUMERIC DEFAULT 20.0,
  preferred_return_pct NUMERIC DEFAULT 8.0,
  fee_offset_pct NUMERIC DEFAULT 0,       -- management fee offset from co-invest
  catch_up_pct NUMERIC DEFAULT 100.0,     -- GP catch-up percentage

  -- Side letter terms
  co_invest_rights BOOLEAN DEFAULT FALSE,
  mfn_clause BOOLEAN DEFAULT FALSE,       -- Most Favoured Nation
  advisory_board_seat BOOLEAN DEFAULT FALSE,
  opt_out_rights JSONB DEFAULT '[]',      -- sectors/geographies LP can opt out of
  side_letter_terms JSONB DEFAULT '{}',   -- catch-all for other terms

  -- Currency
  commitment_currency VARCHAR(3) DEFAULT 'USD',
  fx_rate_at_commitment NUMERIC DEFAULT 1.0,

  -- Status
  status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'redeemed', 'defaulted')),

  -- Audit
  effective_date DATE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  -- Prevent duplicate LP-fund pairs
  UNIQUE(lp_id, fund_id)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_lp_fund_commitments_lp ON lp_fund_commitments(lp_id);
CREATE INDEX IF NOT EXISTS idx_lp_fund_commitments_fund ON lp_fund_commitments(fund_id);

-- Computed view: LP-level summary across all funds
CREATE OR REPLACE VIEW lp_portfolio_summary AS
SELECT
  lp.id AS lp_id,
  lp.name,
  lp.lp_type,
  lp.status AS lp_status,
  COUNT(c.id) AS fund_count,
  SUM(c.commitment_usd) AS total_commitment,
  SUM(c.called_usd) AS total_called,
  SUM(c.distributed_usd) AS total_distributed,
  SUM(c.commitment_usd - c.called_usd) AS total_unfunded,
  CASE WHEN SUM(c.called_usd) > 0
    THEN SUM(c.distributed_usd) / SUM(c.called_usd)
    ELSE 0
  END AS blended_dpi,
  BOOL_OR(c.co_invest_rights) AS has_co_invest_anywhere
FROM limited_partners lp
LEFT JOIN lp_fund_commitments c ON c.lp_id = lp.id
GROUP BY lp.id, lp.name, lp.lp_type, lp.status;

-- Fund-level LP summary
CREATE OR REPLACE VIEW fund_lp_summary AS
SELECT
  c.fund_id,
  c.lp_id,
  lp.name AS lp_name,
  lp.lp_type,
  c.commitment_usd,
  c.called_usd,
  c.distributed_usd,
  (c.commitment_usd - c.called_usd) AS unfunded_usd,
  CASE WHEN c.called_usd > 0
    THEN c.distributed_usd / c.called_usd
    ELSE 0
  END AS dpi,
  c.ownership_pct,
  c.management_fee_pct,
  c.carried_interest_pct,
  c.preferred_return_pct,
  c.co_invest_rights,
  c.mfn_clause,
  c.advisory_board_seat,
  c.side_letter_terms,
  c.status AS commitment_status,
  c.commitment_currency
FROM lp_fund_commitments c
JOIN limited_partners lp ON lp.id = c.lp_id;

-- Update the old view to use the join table
CREATE OR REPLACE VIEW lp_fund_summary AS
SELECT
  lp.id,
  lp.name,
  c.fund_id,
  lp.lp_type,
  c.commitment_usd,
  c.called_usd,
  c.distributed_usd,
  (c.commitment_usd - c.called_usd) AS unfunded_usd,
  CASE WHEN c.called_usd > 0
    THEN c.distributed_usd / c.called_usd
    ELSE 0
  END AS dpi,
  c.vintage_year,
  c.co_invest_rights,
  lp.status
FROM limited_partners lp
LEFT JOIN lp_fund_commitments c ON c.lp_id = lp.id;
