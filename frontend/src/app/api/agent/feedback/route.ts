import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

// Initialize Supabase client with service role key for server-side operations
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseKey = process.env.SUPABASE_SERVICE_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY!;

const supabase = createClient(supabaseUrl, supabaseKey);

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    
    const {
      sessionId,
      prompt,
      response,
      feedbackType,
      feedbackText,
      score,
      modelType,
      corrections,
      timestamp
    } = body;
    
    // Store feedback in Supabase
    const { data, error } = await supabase
      .from('agent_feedback')
      .insert([{
        session_id: sessionId,
        prompt,
        response,
        feedback_type: feedbackType,
        feedback_text: feedbackText,
        score: score || 0,
        model_type: modelType,
        corrections,
        created_at: timestamp || new Date().toISOString(),
        user_id: body.userId || 'anonymous'
      }]);
    
    if (error) {
      console.error('Supabase error:', error);
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
    
    // If this is a correction, create a preference pair for GRPO
    if (corrections || feedbackType === 'semantic') {
      await supabase
        .from('preference_pairs')
        .insert([{
          prompt,
          chosen: corrections || feedbackText,
          rejected: response,
          score_diff: feedbackType === 'good' ? 1.0 : 
                     feedbackType === 'bad' ? -1.0 : 
                     feedbackType === 'edit' ? 0.5 : 0.3,
          model_type: modelType,
          session_id: sessionId,
          created_at: timestamp || new Date().toISOString()
        }]);
    }
    
    return NextResponse.json({ 
      success: true, 
      message: 'Feedback received',
      data 
    });
    
  } catch (error) {
    console.error('Feedback API error:', error);
    return NextResponse.json(
      { error: 'Failed to process feedback' },
      { status: 500 }
    );
  }
}

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const sessionId = searchParams.get('sessionId');
    const modelType = searchParams.get('modelType');
    
    let query = supabase
      .from('agent_feedback')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(100);
    
    if (sessionId) {
      query = query.eq('session_id', sessionId);
    }
    
    if (modelType) {
      query = query.eq('model_type', modelType);
    }
    
    const { data, error } = await query;
    
    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
    
    // Calculate statistics
    const stats = {
      total: data?.length || 0,
      avgScore: data?.reduce((acc, item) => acc + (item.score || 0), 0) / (data?.length || 1),
      byType: data?.reduce((acc: any, item: any) => {
        acc[item.feedback_type] = (acc[item.feedback_type] || 0) + 1;
        return acc;
      }, {}),
      recentFeedback: data?.slice(0, 10)
    };
    
    return NextResponse.json({ 
      success: true,
      stats,
      data 
    });
    
  } catch (error) {
    console.error('Feedback GET error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch feedback' },
      { status: 500 }
    );
  }
}