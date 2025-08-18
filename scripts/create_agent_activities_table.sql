-- Agent Activities Table for Real-time Activity Logging
CREATE TABLE IF NOT EXISTS agent_activities (
  id SERIAL PRIMARY KEY,
  activity_type VARCHAR(50) NOT NULL, -- 'tool_call', 'analysis', 'decision', 'search', 'calculation'
  tool_name VARCHAR(100),
  description TEXT NOT NULL,
  input_data JSONB,
  output_data JSONB,
  confidence_score DECIMAL(3,2), -- 0.00 to 1.00
  session_id VARCHAR(255) DEFAULT 'default',
  timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for efficient querying
CREATE INDEX IF NOT EXISTS idx_agent_activities_timestamp ON agent_activities(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_agent_activities_session ON agent_activities(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_activities_type ON agent_activities(activity_type);

-- Enable Row Level Security
ALTER TABLE agent_activities ENABLE ROW LEVEL SECURITY;

-- Policy to allow all operations (adjust as needed for production)
CREATE POLICY IF NOT EXISTS "Allow all operations on agent_activities"
ON agent_activities FOR ALL
USING (true)
WITH CHECK (true);