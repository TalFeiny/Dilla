import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export async function POST(request: NextRequest) {
  if (!supabaseService) {
    return NextResponse.json({ error: 'Supabase service not configured' }, { status: 503 });
  }

  try {
    const { sessionId, company, modelType, correction, timestamp } = await request.json();

    if (!correction) {
      return NextResponse.json({ error: 'Missing correction field' }, { status: 400 });
    }

    const { data, error } = await supabaseService
      .from('agent_corrections')
      .insert({
        session_id: sessionId,
        company: company || 'general',
        model_type: modelType || 'general',
        correction,
        created_at: timestamp || new Date().toISOString(),
      })
      .select()
      .single();

    if (error) {
      console.error('Failed to store correction:', error);
      return NextResponse.json(
        { error: 'Failed to store correction', details: error.message },
        { status: 500 },
      );
    }

    return NextResponse.json({ success: true, id: data.id });
  } catch (error) {
    console.error('Corrections endpoint error:', error);
    return NextResponse.json({ error: 'Failed to process correction' }, { status: 500 });
  }
}
