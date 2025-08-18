import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export async function POST() {
  try {
    // Create the agent_activities table
    const createTableSQL = `
      CREATE TABLE IF NOT EXISTS agent_activities (
        id SERIAL PRIMARY KEY,
        activity_type VARCHAR(50) NOT NULL,
        tool_name VARCHAR(100),
        description TEXT NOT NULL,
        input_data JSONB,
        output_data JSONB,
        confidence_score DECIMAL(3,2),
        session_id VARCHAR(255) DEFAULT 'default',
        timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
      );

      -- Create indexes
      CREATE INDEX IF NOT EXISTS idx_agent_activities_timestamp ON agent_activities(timestamp DESC);
      CREATE INDEX IF NOT EXISTS idx_agent_activities_session ON agent_activities(session_id);
      CREATE INDEX IF NOT EXISTS idx_agent_activities_type ON agent_activities(activity_type);

      -- Enable RLS
      ALTER TABLE agent_activities ENABLE ROW LEVEL SECURITY;

      -- Create policy
      DO $$ 
      BEGIN
        IF NOT EXISTS (
          SELECT 1 FROM pg_policies 
          WHERE tablename = 'agent_activities' 
          AND policyname = 'Allow all operations on agent_activities'
        ) THEN
          CREATE POLICY "Allow all operations on agent_activities"
          ON agent_activities FOR ALL
          USING (true)
          WITH CHECK (true);
        END IF;
      END $$;
    `;

    const { error } = await supabase.rpc('exec_sql', { 
      sql: createTableSQL 
    });

    if (error) {
      throw error;
    }

    // Test insert a sample activity
    const { data: testData, error: insertError } = await supabase
      .from('agent_activities')
      .insert({
        activity_type: 'setup',
        description: 'Agent activities table created and tested',
        input_data: { setup: true },
        session_id: 'setup'
      })
      .select();

    if (insertError) {
      console.warn('Insert test failed:', insertError);
    }

    return NextResponse.json({
      success: true,
      message: 'Agent activities table created successfully',
      testData
    });

  } catch (error) {
    console.error('Setup error:', error);
    return NextResponse.json({
      error: 'Setup failed',
      details: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
}