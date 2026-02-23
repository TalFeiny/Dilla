-- Persist rejected document suggestions so they are filtered out of GET /api/matrix/suggestions.
-- suggestion_id format: "suggestion-{doc_id}-{columnKey}" (e.g. suggestion-123-arr).

CREATE TABLE IF NOT EXISTS rejected_suggestions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fund_id UUID NOT NULL REFERENCES funds(id) ON DELETE CASCADE,
  suggestion_id TEXT NOT NULL,
  rejected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(fund_id, suggestion_id)
);

CREATE INDEX IF NOT EXISTS idx_rejected_suggestions_fund_id ON rejected_suggestions(fund_id);
CREATE INDEX IF NOT EXISTS idx_rejected_suggestions_suggestion_id ON rejected_suggestions(suggestion_id);

ALTER TABLE rejected_suggestions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow read rejected_suggestions for fund"
  ON rejected_suggestions FOR SELECT USING (true);

CREATE POLICY "Allow insert rejected_suggestions for fund"
  ON rejected_suggestions FOR INSERT WITH CHECK (true);

CREATE POLICY "Allow update rejected_suggestions for fund"
  ON rejected_suggestions FOR UPDATE USING (true) WITH CHECK (true);

COMMENT ON TABLE rejected_suggestions IS 'User-rejected document-to-matrix suggestions; GET suggestions filters these out.';
