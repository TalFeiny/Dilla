-- Fix pending_suggestions rows written with backend field names instead of
-- frontend grid column IDs, and fix string-serialized suggested_value / metadata.
--
-- Column ID renames: align with frontend grid expectations.

BEGIN;

-- 1. Remap column_id values from backend names → frontend column IDs
UPDATE pending_suggestions SET column_id = 'valuation'
  WHERE column_id IN ('currentValuation', 'currentValuationUsd', 'current_valuation_usd', 'inferred_valuation');

UPDATE pending_suggestions SET column_id = 'burnRate'
  WHERE column_id IN ('burnRateMonthlyUsd', 'burn_rate_monthly_usd', 'burn_rate');

UPDATE pending_suggestions SET column_id = 'revenueGrowthAnnual'
  WHERE column_id IN ('revenueGrowthAnnualPct', 'revenue_growth_annual_pct', 'growth_rate');

UPDATE pending_suggestions SET column_id = 'runway'
  WHERE column_id IN ('runwayMonths', 'runway_months');

UPDATE pending_suggestions SET column_id = 'arr'
  WHERE column_id IN ('revenue', 'inferred_revenue');

UPDATE pending_suggestions SET column_id = 'headcount'
  WHERE column_id IN ('employee_count', 'team_size');

UPDATE pending_suggestions SET column_id = 'totalRaised'
  WHERE column_id IN ('total_raised', 'total_funding');

UPDATE pending_suggestions SET column_id = 'cashInBank'
  WHERE column_id IN ('cash_balance', 'cash_in_bank_usd');

UPDATE pending_suggestions SET column_id = 'grossMargin'
  WHERE column_id = 'gross_margin';

UPDATE pending_suggestions SET column_id = 'revenueGrowthMonthly'
  WHERE column_id IN ('revenueGrowthMonthlyPct', 'revenue_growth_monthly_pct');

UPDATE pending_suggestions SET column_id = 'stage'
  WHERE column_id = 'funding_stage';

UPDATE pending_suggestions SET column_id = 'businessModel'
  WHERE column_id = 'business_model';

UPDATE pending_suggestions SET column_id = 'hqLocation'
  WHERE column_id = 'hq_location';

UPDATE pending_suggestions SET column_id = 'foundedYear'
  WHERE column_id = 'founded_year';

UPDATE pending_suggestions SET column_id = 'targetMarket'
  WHERE column_id = 'target_market';

UPDATE pending_suggestions SET column_id = 'pricingModel'
  WHERE column_id = 'pricing_model';

-- 2. Fix suggested_value that was double-serialized as a JSON string
--    e.g. '"{\\"value\\": 123}"' instead of '{"value": 123}'
--    Detect: jsonb_typeof returns 'string' and the string parses as valid JSON
UPDATE pending_suggestions
  SET suggested_value = suggested_value #>> '{}' :: jsonb
  WHERE jsonb_typeof(suggested_value) = 'string'
    AND (suggested_value #>> '{}') :: jsonb IS NOT NULL;

-- 3. Fix metadata that was double-serialized as a JSON string
UPDATE pending_suggestions
  SET metadata = metadata #>> '{}' :: jsonb
  WHERE metadata IS NOT NULL
    AND jsonb_typeof(metadata) = 'string'
    AND (metadata #>> '{}') :: jsonb IS NOT NULL;

-- 4. Wrap bare scalar suggested_value in {"value": ...} for consistency
--    e.g. if suggested_value is just 42 or "some string", wrap it
UPDATE pending_suggestions
  SET suggested_value = jsonb_build_object('value', suggested_value)
  WHERE jsonb_typeof(suggested_value) IN ('number', 'string', 'boolean', 'null')
    AND NOT (jsonb_typeof(suggested_value) = 'string' AND suggested_value #>> '{}' LIKE '{%');

COMMIT;
