-- Create RL tables for saving agent outputs and feedback
-- This allows us to track and improve our AI models based on user feedback

-- Table for storing agent outputs/experiences
CREATE TABLE IF NOT EXISTS rl_experiences (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  session_id TEXT NOT NULL,
  prompt TEXT NOT NULL,
  output_format TEXT NOT NULL CHECK (output_format IN ('docs', 'deck', 'spreadsheet', 'matrix', 'analysis', 'markdown')),
  output_data JSONB NOT NULL,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table for storing user feedback on outputs
CREATE TABLE IF NOT EXISTS rl_feedback (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  experience_id UUID REFERENCES rl_experiences(id) ON DELETE CASCADE,
  session_id TEXT NOT NULL,
  feedback_type TEXT NOT NULL CHECK (feedback_type IN ('positive', 'negative', 'correction', 'semantic')),
  feedback_text TEXT,
  corrected_output JSONB,
  reward_score FLOAT CHECK (reward_score >= -1 AND reward_score <= 1),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_rl_experiences_session ON rl_experiences(session_id);
CREATE INDEX IF NOT EXISTS idx_rl_experiences_format ON rl_experiences(output_format);
CREATE INDEX IF NOT EXISTS idx_rl_experiences_created ON rl_experiences(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rl_feedback_experience ON rl_feedback(experience_id);
CREATE INDEX IF NOT EXISTS idx_rl_feedback_type ON rl_feedback(feedback_type);
CREATE INDEX IF NOT EXISTS idx_rl_feedback_score ON rl_feedback(reward_score);

-- Enable Row Level Security
ALTER TABLE rl_experiences ENABLE ROW LEVEL SECURITY;
ALTER TABLE rl_feedback ENABLE ROW LEVEL SECURITY;

-- Policies for anonymous access (adjust based on your auth needs)
CREATE POLICY "Allow anonymous insert on rl_experiences" ON rl_experiences
  FOR INSERT WITH CHECK (true);

CREATE POLICY "Allow anonymous select on rl_experiences" ON rl_experiences
  FOR SELECT USING (true);

CREATE POLICY "Allow anonymous insert on rl_feedback" ON rl_feedback
  FOR INSERT WITH CHECK (true);

CREATE POLICY "Allow anonymous select on rl_feedback" ON rl_feedback
  FOR SELECT USING (true);

-- Function to get aggregated stats
CREATE OR REPLACE FUNCTION get_rl_stats(format_filter TEXT DEFAULT NULL)
RETURNS TABLE (
  total_experiences BIGINT,
  total_feedback BIGINT,
  avg_reward_score FLOAT,
  positive_feedback_rate FLOAT,
  format_breakdown JSONB
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    COUNT(DISTINCT e.id) as total_experiences,
    COUNT(f.id) as total_feedback,
    AVG(f.reward_score) as avg_reward_score,
    COUNT(CASE WHEN f.feedback_type = 'positive' THEN 1 END)::FLOAT / NULLIF(COUNT(f.id), 0) as positive_feedback_rate,
    jsonb_object_agg(
      COALESCE(e.output_format, 'unknown'),
      format_counts.count
    ) as format_breakdown
  FROM rl_experiences e
  LEFT JOIN rl_feedback f ON e.id = f.experience_id
  LEFT JOIN LATERAL (
    SELECT output_format, COUNT(*) as count
    FROM rl_experiences
    WHERE format_filter IS NULL OR output_format = format_filter
    GROUP BY output_format
  ) format_counts ON format_counts.output_format = e.output_format
  WHERE format_filter IS NULL OR e.output_format = format_filter
  GROUP BY format_counts.count;
END;
$$ LANGUAGE plpgsql;

-- Sample data for testing (optional)
/*
INSERT INTO rl_experiences (session_id, prompt, output_format, output_data, metadata)
VALUES 
  ('test-session-1', 'Compare @Ramp and @Brex', 'matrix', '{"companies": ["Ramp", "Brex"], "metrics": {}}', '{"test": true}'),
  ('test-session-2', 'Create pitch deck for Series A', 'deck', '{"slides": []}', '{"test": true}');

INSERT INTO rl_feedback (experience_id, session_id, feedback_type, feedback_text, reward_score)
SELECT 
  id, 
  session_id, 
  'positive', 
  'Great analysis!', 
  0.9
FROM rl_experiences 
WHERE session_id = 'test-session-1'
LIMIT 1;
*/

COMMENT ON TABLE rl_experiences IS 'Stores AI agent outputs for different formats (docs, decks, spreadsheets, etc)';
COMMENT ON TABLE rl_feedback IS 'Stores user feedback on AI outputs for model improvement';
COMMENT ON COLUMN rl_experiences.output_format IS 'Format type: docs, deck, spreadsheet, matrix, analysis, markdown';
COMMENT ON COLUMN rl_feedback.reward_score IS 'Score from -1 (very bad) to 1 (very good)';