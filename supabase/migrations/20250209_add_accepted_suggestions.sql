-- Persist accepted document suggestions so GET /api/matrix/suggestions filters them out
-- (avoids accepted suggestions reappearing after refresh). suggestion_id format matches
-- document suggestions: "suggestion-{doc_id}-{columnKey}" (e.g. suggestion-123-arr).

CREATE TABLE IF NOT EXISTS accepted_suggestions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fund_id UUID NOT NULL REFERENCES funds(id) ON DELETE CASCADE,
  suggestion_id TEXT NOT NULL,
  accepted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(fund_id, suggestion_id)
);

CREATE INDEX IF NOT EXISTS idx_accepted_suggestions_fund_id ON accepted_suggestions(fund_id);
CREATE INDEX IF NOT EXISTS idx_accepted_suggestions_suggestion_id ON accepted_suggestions(suggestion_id);

ALTER TABLE accepted_suggestions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow read accepted_suggestions for fund"
  ON accepted_suggestions FOR SELECT USING (true);

CREATE POLICY "Allow insert accepted_suggestions for fund"
  ON accepted_suggestions FOR INSERT WITH CHECK (true);

CREATE POLICY "Allow update accepted_suggestions for fund"
  ON accepted_suggestions FOR UPDATE USING (true) WITH CHECK (true);

COMMENT ON TABLE accepted_suggestions IS 'User-accepted document-to-matrix suggestions; GET suggestions filters these out so they do not reappear after refresh.';
