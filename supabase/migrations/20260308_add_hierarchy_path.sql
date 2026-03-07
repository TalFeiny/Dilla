-- ============================================================
-- Migration: ERP hierarchy support for fpa_actuals
-- Handles: QBO, Xero, NetSuite, SAP, Sage, Dynamics, Zoho, MYOB
-- ============================================================

-- 1. Add hierarchy columns to fpa_actuals
ALTER TABLE fpa_actuals
  ADD COLUMN IF NOT EXISTS hierarchy_path text NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS erp_account_code text DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS depth smallint NOT NULL DEFAULT 0;

-- 2. Backfill hierarchy_path from existing category+subcategory
UPDATE fpa_actuals SET hierarchy_path = CASE
  WHEN subcategory = '' OR subcategory IS NULL THEN category
  ELSE category || '/' || subcategory
END
WHERE hierarchy_path = '';

-- 3. Backfill depth
UPDATE fpa_actuals SET depth = CASE
  WHEN subcategory = '' OR subcategory IS NULL THEN 0
  ELSE 1
END
WHERE depth = 0 AND hierarchy_path != '';

-- 4. Replace unique index to include hierarchy_path
DROP INDEX IF EXISTS idx_fpa_actuals_dedup;
DROP INDEX IF EXISTS idx_fpa_actuals_dedup_v2;

CREATE UNIQUE INDEX idx_fpa_actuals_dedup
  ON fpa_actuals (company_id, period, category, subcategory, hierarchy_path, source);

-- 5. Indexes for fast hierarchy queries
CREATE INDEX IF NOT EXISTS idx_fpa_actuals_hierarchy
  ON fpa_actuals (company_id, hierarchy_path);

CREATE INDEX IF NOT EXISTS idx_fpa_actuals_erp_code
  ON fpa_actuals (company_id, erp_account_code)
  WHERE erp_account_code IS NOT NULL;

-- 6. Lookup table: per-company ERP account code → internal category mapping
CREATE TABLE IF NOT EXISTS erp_account_mappings (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  company_id text NOT NULL,
  erp_source text NOT NULL DEFAULT 'unknown',
  account_code text NOT NULL,
  account_name text NOT NULL DEFAULT '',
  parent_code text DEFAULT NULL,
  depth smallint NOT NULL DEFAULT 0,
  mapped_category text DEFAULT NULL,
  mapped_subcategory text DEFAULT NULL,
  hierarchy_path text NOT NULL DEFAULT '',
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  UNIQUE (company_id, erp_source, account_code)
);

-- 7. Universal account-code-range → category patterns
CREATE TABLE IF NOT EXISTS erp_account_code_patterns (
  id serial PRIMARY KEY,
  erp_source text NOT NULL DEFAULT '*',
  code_pattern text DEFAULT NULL,
  code_range_start text DEFAULT NULL,
  code_range_end text DEFAULT NULL,
  mapped_category text NOT NULL,
  description text DEFAULT ''
);

-- Seed: standard numeric ranges (NetSuite / SAP / MYOB / Dynamics convention)
INSERT INTO erp_account_code_patterns (erp_source, code_range_start, code_range_end, mapped_category, description) VALUES
  ('*', '4000', '4999', 'revenue',     'Revenue / Income accounts'),
  ('*', '5000', '5999', 'cogs',        'Cost of Goods Sold'),
  ('*', '6000', '6199', 'opex_rd',     'R&D / Engineering expenses'),
  ('*', '6200', '6399', 'opex_sm',     'Sales & Marketing expenses'),
  ('*', '6400', '6599', 'opex_ga',     'General & Administrative'),
  ('*', '6600', '6999', 'opex_total',  'Other operating expenses'),
  ('*', '7000', '7999', 'opex_total',  'Other operating expenses'),
  -- Xero (shorter codes)
  ('xero', '200', '299', 'revenue',    'Xero revenue accounts'),
  ('xero', '300', '399', 'cogs',       'Xero direct costs'),
  ('xero', '400', '499', 'opex_total', 'Xero operating expenses'),
  -- SAP (6-digit)
  ('sap', '400000', '499999', 'revenue',    'SAP revenue accounts'),
  ('sap', '500000', '599999', 'cogs',       'SAP COGS accounts'),
  ('sap', '600000', '699999', 'opex_total', 'SAP operating expenses')
ON CONFLICT DO NOTHING;

-- 8. Helper: QBO colon-separated path → slash path
CREATE OR REPLACE FUNCTION normalize_qbo_path(qbo_path text)
RETURNS text LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
  RETURN lower(replace(replace(qbo_path, ':', '/'), ' ', '_'));
END;
$$;

-- 9. Helper: resolve category from account code via range table
CREATE OR REPLACE FUNCTION resolve_category_by_code(
  p_account_code text,
  p_erp_source text DEFAULT '*'
)
RETURNS text LANGUAGE plpgsql STABLE AS $$
DECLARE
  result text;
BEGIN
  SELECT mapped_category INTO result
  FROM erp_account_code_patterns
  WHERE (erp_source = p_erp_source OR erp_source = '*')
    AND p_account_code >= code_range_start
    AND p_account_code <= code_range_end
  ORDER BY
    CASE WHEN erp_source = p_erp_source THEN 0 ELSE 1 END,
    code_range_start DESC
  LIMIT 1;
  RETURN result;
END;
$$;

-- 10. View: exploded hierarchy tree for any company
CREATE OR REPLACE VIEW v_fpa_hierarchy AS
SELECT
  company_id,
  hierarchy_path,
  category,
  subcategory,
  depth,
  CASE
    WHEN position('/' in hierarchy_path) > 0
    THEN left(hierarchy_path, length(hierarchy_path) - position('/' in reverse(hierarchy_path)))
    ELSE NULL
  END AS parent_path,
  CASE
    WHEN position('/' in hierarchy_path) > 0
    THEN split_part(hierarchy_path, '/', array_length(string_to_array(hierarchy_path, '/'), 1))
    ELSE hierarchy_path
  END AS leaf_label,
  period,
  amount,
  source
FROM fpa_actuals
WHERE hierarchy_path != '';
