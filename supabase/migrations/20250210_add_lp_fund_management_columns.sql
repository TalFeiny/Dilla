-- Add fund-management columns to limited_partners table
-- These sit alongside the existing investor-relations columns (name, lp_type, contact_*, etc.)

ALTER TABLE limited_partners
  ADD COLUMN IF NOT EXISTS fund_id UUID,
  ADD COLUMN IF NOT EXISTS commitment_usd NUMERIC DEFAULT 0,
  ADD COLUMN IF NOT EXISTS called_usd NUMERIC DEFAULT 0,
  ADD COLUMN IF NOT EXISTS distributed_usd NUMERIC DEFAULT 0,
  ADD COLUMN IF NOT EXISTS vintage_year INTEGER,
  ADD COLUMN IF NOT EXISTS co_invest_rights BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS side_letter_terms JSONB DEFAULT '{}';

-- Computed view for unfunded commitment + DPI
CREATE OR REPLACE VIEW lp_fund_summary AS
SELECT
  lp.id,
  lp.name,
  lp.fund_id,
  lp.lp_type,
  lp.commitment_usd,
  lp.called_usd,
  lp.distributed_usd,
  (lp.commitment_usd - lp.called_usd) AS unfunded_usd,
  CASE WHEN lp.called_usd > 0
    THEN lp.distributed_usd / lp.called_usd
    ELSE 0
  END AS dpi,
  lp.vintage_year,
  lp.co_invest_rights,
  lp.status
FROM limited_partners lp;

-- Index for fund_id lookups
CREATE INDEX IF NOT EXISTS idx_limited_partners_fund_id ON limited_partners (fund_id);
