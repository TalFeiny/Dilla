-- Loveable-style subscription system tables
-- One free generation → immediate paywall → seat-based pricing

-- Organizations table for team/company accounts
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    domain TEXT, -- e.g., company.com for auto-grouping users
    stripe_customer_id TEXT UNIQUE,
    stripe_subscription_id TEXT,
    subscription_tier TEXT DEFAULT 'free' CHECK (subscription_tier IN ('free', 'starter', 'professional', 'enterprise')),
    subscription_status TEXT DEFAULT 'inactive' CHECK (subscription_status IN ('inactive', 'active', 'past_due', 'cancelled')),
    seats_purchased INTEGER DEFAULT 1,
    seats_used INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Users table with Google auth support
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    google_id TEXT UNIQUE,
    name TEXT,
    avatar_url TEXT,
    organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    role TEXT DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member')),
    is_active BOOLEAN DEFAULT true,
    free_generation_used BOOLEAN DEFAULT false,
    stripe_customer_id TEXT, -- For individual billing if needed
    session_token TEXT,
    last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Anonymous sessions for tracking free generations
CREATE TABLE IF NOT EXISTS anonymous_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT UNIQUE NOT NULL, -- Browser fingerprint or cookie
    ip_address INET,
    user_agent TEXT,
    free_generation_used BOOLEAN DEFAULT false,
    converted_user_id UUID REFERENCES users(id), -- If they sign up later
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() + INTERVAL '7 days'
);

-- Generation history for all users (anonymous and registered)
CREATE TABLE IF NOT EXISTS generations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    anonymous_session_id UUID REFERENCES anonymous_sessions(id),
    organization_id UUID REFERENCES organizations(id),
    prompt TEXT NOT NULL,
    response TEXT,
    model_used TEXT NOT NULL,
    tokens_input INTEGER DEFAULT 0,
    tokens_output INTEGER DEFAULT 0,
    cost_cents INTEGER DEFAULT 0, -- Track cost in cents
    is_free_generation BOOLEAN DEFAULT false,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Active user sessions for seat management
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    session_token TEXT UNIQUE NOT NULL,
    ip_address INET,
    user_agent TEXT,
    device_fingerprint TEXT, -- For detecting multiple devices
    is_active BOOLEAN DEFAULT true,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() + INTERVAL '30 days'
);

-- Organization invitations
CREATE TABLE IF NOT EXISTS organization_invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    role TEXT DEFAULT 'member' CHECK (role IN ('admin', 'member')),
    invited_by UUID REFERENCES users(id),
    token TEXT UNIQUE NOT NULL,
    accepted BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() + INTERVAL '7 days'
);

-- Usage tracking for billing
CREATE TABLE IF NOT EXISTS usage_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    record_type TEXT NOT NULL CHECK (record_type IN ('generation', 'api_call', 'export', 'analysis')),
    quantity INTEGER DEFAULT 1,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Model access control configuration
CREATE TABLE IF NOT EXISTS model_tiers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tier TEXT NOT NULL CHECK (tier IN ('free', 'starter', 'professional', 'enterprise')),
    model_id TEXT NOT NULL,
    model_name TEXT NOT NULL,
    max_tokens INTEGER DEFAULT 4000,
    rate_limit_per_day INTEGER, -- NULL means unlimited
    cost_per_1k_tokens INTEGER, -- in cents
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default model configurations
INSERT INTO model_tiers (tier, model_id, model_name, max_tokens, rate_limit_per_day, cost_per_1k_tokens) VALUES
-- Free tier (anonymous users get one shot)
('free', 'gpt-4o-mini', 'GPT-4o Mini', 2000, 1, 1),

-- Starter tier
('starter', 'gpt-4o-mini', 'GPT-4o Mini', 4000, 100, 1),
('starter', 'claude-3-haiku-20240307', 'Claude 3 Haiku', 4000, 100, 2),

-- Professional tier
('professional', 'gpt-4o-mini', 'GPT-4o Mini', 8000, 500, 1),
('professional', 'gpt-4o', 'GPT-4o', 8000, 200, 5),
('professional', 'claude-3-haiku-20240307', 'Claude 3 Haiku', 8000, 500, 2),
('professional', 'claude-3-5-sonnet-20241022', 'Claude 3.5 Sonnet', 8000, 200, 10),

-- Enterprise tier (unlimited access)
('enterprise', 'gpt-4o-mini', 'GPT-4o Mini', 32000, NULL, 1),
('enterprise', 'gpt-4o', 'GPT-4o', 32000, NULL, 5),
('enterprise', 'claude-3-haiku-20240307', 'Claude 3 Haiku', 32000, NULL, 2),
('enterprise', 'claude-3-5-sonnet-20241022', 'Claude 3.5 Sonnet', 32000, NULL, 10),
('enterprise', 'claude-3-opus-20240229', 'Claude 3 Opus', 32000, NULL, 30),
('enterprise', 'o1-preview', 'OpenAI o1 Preview', 32000, NULL, 50);

-- Indexes for performance
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_google_id ON users(google_id);
CREATE INDEX idx_users_organization ON users(organization_id);
CREATE INDEX idx_sessions_user ON user_sessions(user_id);
CREATE INDEX idx_sessions_org ON user_sessions(organization_id);
CREATE INDEX idx_sessions_active ON user_sessions(is_active, last_activity);
CREATE INDEX idx_generations_user ON generations(user_id);
CREATE INDEX idx_generations_session ON generations(anonymous_session_id);
CREATE INDEX idx_generations_created ON generations(created_at);
CREATE INDEX idx_anonymous_sessions_session_id ON anonymous_sessions(session_id);
CREATE INDEX idx_invitations_token ON organization_invitations(token);
CREATE INDEX idx_invitations_email ON organization_invitations(email);

-- Triggers for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_organizations_updated_at BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to check seat availability
CREATE OR REPLACE FUNCTION check_seat_availability(org_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    seats_purchased INTEGER;
    active_sessions INTEGER;
BEGIN
    SELECT o.seats_purchased INTO seats_purchased
    FROM organizations o
    WHERE o.id = org_id;
    
    SELECT COUNT(*) INTO active_sessions
    FROM user_sessions s
    WHERE s.organization_id = org_id
    AND s.is_active = true
    AND s.last_activity > NOW() - INTERVAL '30 minutes';
    
    RETURN active_sessions < seats_purchased;
END;
$$ LANGUAGE plpgsql;

-- Function to clean up inactive sessions
CREATE OR REPLACE FUNCTION cleanup_inactive_sessions()
RETURNS void AS $$
BEGIN
    UPDATE user_sessions
    SET is_active = false
    WHERE is_active = true
    AND last_activity < NOW() - INTERVAL '30 minutes';
    
    -- Update seats_used count
    UPDATE organizations o
    SET seats_used = (
        SELECT COUNT(DISTINCT user_id)
        FROM user_sessions s
        WHERE s.organization_id = o.id
        AND s.is_active = true
    );
END;
$$ LANGUAGE plpgsql;