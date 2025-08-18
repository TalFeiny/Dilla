import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export async function GET() {
  try {
    const { data, error } = await supabase
      .from('agent_activities')
      .select('*')
      .order('timestamp', { ascending: false })
      .limit(20);

    if (error) {
      return NextResponse.json({ 
        error: 'Database error', 
        details: error.message,
        activities: []
      });
    }

    return NextResponse.json({
      activities: data || [],
      count: data?.length || 0,
      message: data?.length ? 'Activities found' : 'No activities yet - may need to create table'
    });
  } catch (error) {
    return NextResponse.json({
      error: 'Server error',
      details: error instanceof Error ? error.message : 'Unknown error',
      activities: []
    });
  }
}