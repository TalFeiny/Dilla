import { NextRequest, NextResponse } from 'next/server';
import { supabaseService } from '@/lib/supabase';

export async function POST(request: NextRequest) {
  if (!supabaseService) {
    return NextResponse.json({ error: 'Supabase service not configured' }, { status: 503 });
  }

  try {
    const { 
      sessionId, 
      query, 
      response, 
      feedback, 
      score,
      company,
      agent 
    } = await request.json();
    
    console.log(`📝 Storing RL feedback for ${company || 'general'}`);
    
    // Store in model_corrections table which actually exists
    if (!supabaseService) {
      return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
    }
    const { data, error } = await supabaseService
      .from('model_corrections')
      .insert({
        company_name: company || 'general',
        model_type: agent || 'general',
        correction_type: score > 0 ? 'positive' : 'negative',
        feedback: feedback || '',
        learning_patterns: {
          query,
          response: response?.substring(0, 1000),
          sessionId,
          score
        },
        confidence: Math.abs(score),
        metadata: {
          session_id: sessionId,
          timestamp: new Date().toISOString()
        }
      })
      .select()
      .single();
    
    if (error) {
      console.error('Failed to store RL feedback:', error);
      console.error('Error details:', JSON.stringify(error, null, 2));
      return NextResponse.json(
        { error: 'Failed to store feedback', details: error.message || error },
        { status: 500 }
      );
    }
    
    console.log(`✅ RL feedback stored with ID: ${data.id}`);
    
    return NextResponse.json({
      success: true,
      id: data.id,
      message: 'Feedback stored successfully'
    });
    
  } catch (error) {
    console.error('RL storage error:', error);
    return NextResponse.json(
      { error: 'Failed to process feedback' },
      { status: 500 }
    );
  }
}