-- Fix: pending_suggestions has no unique constraint on (fund_id, company_id, column_id),
-- so every skill run creates duplicates. Accept/reject deletes ONE row but the duplicate stays.
--
-- Step 1: Delete existing duplicates (keep the newest row per group).
-- Step 2: Add unique constraint so future inserts can use ON CONFLICT (upsert).

DELETE FROM pending_suggestions
WHERE id NOT IN (
  SELECT DISTINCT ON (fund_id, company_id, column_id) id
  FROM pending_suggestions
  ORDER BY fund_id, company_id, column_id, created_at DESC
);

ALTER TABLE pending_suggestions
  ADD CONSTRAINT uq_pending_suggestions_fund_company_column
  UNIQUE (fund_id, company_id, column_id);
