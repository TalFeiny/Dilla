-- Fix unique index to include subcategory so that multiple subcategories
-- under the same parent category don't collide during upsert.
--
-- Step 1: Backfill existing NULL subcategory values to empty string
-- Step 2: Set column default to empty string + NOT NULL
-- Step 3: Replace unique index to include subcategory

-- Backfill NULLs
UPDATE fpa_actuals SET subcategory = '' WHERE subcategory IS NULL;

-- Make subcategory non-nullable with empty string default
ALTER TABLE fpa_actuals ALTER COLUMN subcategory SET DEFAULT '';
ALTER TABLE fpa_actuals ALTER COLUMN subcategory SET NOT NULL;

-- Replace unique index
DROP INDEX IF EXISTS idx_fpa_actuals_dedup;

CREATE UNIQUE INDEX idx_fpa_actuals_dedup
ON fpa_actuals (company_id, period, category, subcategory, source);
