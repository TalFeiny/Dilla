-- Agent State Management Tables
-- Store conversation history and context persistently

-- Create agent conversations table
CREATE TABLE IF NOT EXISTS agent_conversations (
    id VARCHAR(255) PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    messages JSONB DEFAULT '[]'::jsonb,
    context JSONB DEFAULT '{}'::jsonb,
    summary TEXT,
    tags TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_agent_conversations_user_id ON agent_conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_conversations_updated_at ON agent_conversations(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_conversations_messages ON agent_conversations USING GIN(messages);
CREATE INDEX IF NOT EXISTS idx_agent_conversations_context ON agent_conversations USING GIN(context);
CREATE INDEX IF NOT EXISTS idx_agent_conversations_tags ON agent_conversations USING GIN(tags);

-- Full text search on messages
ALTER TABLE agent_conversations ADD COLUMN IF NOT EXISTS messages_search tsvector 
    GENERATED ALWAYS AS (to_tsvector('english', messages::text)) STORED;
CREATE INDEX IF NOT EXISTS idx_agent_conversations_search ON agent_conversations USING GIN(messages_search);

-- Agent memory table for long-term knowledge
CREATE TABLE IF NOT EXISTS agent_memory (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    memory_type VARCHAR(50) NOT NULL, -- 'company', 'person', 'fact', 'preference'
    entity_name VARCHAR(255),
    entity_id UUID,
    facts JSONB DEFAULT '{}'::jsonb,
    embeddings vector(1536), -- For semantic search if using OpenAI embeddings
    source_conversation_id VARCHAR(255) REFERENCES agent_conversations(id),
    confidence_score DECIMAL(3,2) DEFAULT 1.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE -- For temporary memories
);

-- Indexes for agent memory
CREATE INDEX IF NOT EXISTS idx_agent_memory_type ON agent_memory(memory_type);
CREATE INDEX IF NOT EXISTS idx_agent_memory_entity ON agent_memory(entity_name);
CREATE INDEX IF NOT EXISTS idx_agent_memory_facts ON agent_memory USING GIN(facts);

-- Agent tools usage tracking
CREATE TABLE IF NOT EXISTS agent_tool_usage (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    conversation_id VARCHAR(255) REFERENCES agent_conversations(id),
    tool_name VARCHAR(100) NOT NULL,
    parameters JSONB,
    result JSONB,
    execution_time_ms INTEGER,
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for tool usage analytics
CREATE INDEX IF NOT EXISTS idx_agent_tool_usage_conversation ON agent_tool_usage(conversation_id);
CREATE INDEX IF NOT EXISTS idx_agent_tool_usage_tool ON agent_tool_usage(tool_name);
CREATE INDEX IF NOT EXISTS idx_agent_tool_usage_created ON agent_tool_usage(created_at DESC);

-- Agent feedback table for learning
CREATE TABLE IF NOT EXISTS agent_feedback (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    conversation_id VARCHAR(255) REFERENCES agent_conversations(id),
    message_id VARCHAR(255),
    feedback_type VARCHAR(50), -- 'helpful', 'not_helpful', 'correction', 'preference'
    feedback_value JSONB,
    user_id UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Row Level Security Policies
ALTER TABLE agent_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_tool_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_feedback ENABLE ROW LEVEL SECURITY;

-- Users can only see their own conversations
CREATE POLICY "Users can view own conversations" ON agent_conversations
    FOR SELECT USING (auth.uid() = user_id OR user_id IS NULL);

CREATE POLICY "Users can create own conversations" ON agent_conversations
    FOR INSERT WITH CHECK (auth.uid() = user_id OR user_id IS NULL);

CREATE POLICY "Users can update own conversations" ON agent_conversations
    FOR UPDATE USING (auth.uid() = user_id OR user_id IS NULL);

-- Function to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_agent_conversations_updated_at BEFORE UPDATE ON agent_conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_agent_memory_updated_at BEFORE UPDATE ON agent_memory
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to clean up old conversations
CREATE OR REPLACE FUNCTION cleanup_old_conversations()
RETURNS void AS $$
BEGIN
    -- Delete conversations older than 30 days with no user_id
    DELETE FROM agent_conversations 
    WHERE user_id IS NULL 
    AND updated_at < NOW() - INTERVAL '30 days';
    
    -- Archive conversations older than 90 days
    UPDATE agent_conversations 
    SET messages = jsonb_build_object(
        'archived', true,
        'message_count', jsonb_array_length(messages),
        'summary', COALESCE(summary, 'Archived conversation')
    )
    WHERE updated_at < NOW() - INTERVAL '90 days'
    AND jsonb_array_length(messages) > 50;
END;
$$ language 'plpgsql';

-- Schedule cleanup (requires pg_cron extension)
-- SELECT cron.schedule('cleanup-old-conversations', '0 2 * * *', 'SELECT cleanup_old_conversations();');