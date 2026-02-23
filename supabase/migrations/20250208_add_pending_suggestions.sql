-- Pending suggestions from services (valuation, PWERM, etc.)
-- Wrapper intercepts cell action results; they go here until user accepts/rejects.
-- GET /api/matrix/suggestions merges document + pending suggestions into one feed.

CREATE TABLE IF NOT EXISTS pending_suggestions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fund_id UUID NOT NULL REFERENCES funds(id) ON DELETE CASCADE,
  company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  column_id TEXT NOT NULL,
  suggested_value JSONB NOT NULL,
  source_service TEXT NOT NULL,
  reasoning TEXT,
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  batch_id UUID
);

CREATE INDEX IF NOT EXISTS idx_pending_suggestions_fund ON pending_suggestions(fund_id);
CREATE INDEX IF NOT EXISTS idx_pending_suggestions_company ON pending_suggestions(company_id);
CREATE INDEX IF NOT EXISTS idx_pending_suggestions_created ON pending_suggestions(created_at DESC);

ALTER TABLE pending_suggestions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow read pending_suggestions" ON pending_suggestions FOR SELECT USING (true);
CREATE POLICY "Allow insert pending_suggestions" ON pending_suggestions FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow update pending_suggestions" ON pending_suggestions FOR UPDATE USING (true) WITH CHECK (true);
CREATE POLICY "Allow delete pending_suggestions" ON pending_suggestions FOR DELETE USING (true);

COMMENT ON TABLE pending_suggestions IS 'Service-originated suggestions (valuation, PWERM, etc.); merged with document suggestions in GET; accepted/rejected via wrapper flow.';
