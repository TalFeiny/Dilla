import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

// POST: Store new experience
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      state_embedding,
      action_embedding,
      next_state_embedding,
      reward,
      metadata
    } = body;
    
    // Validate embeddings dimension
    if (state_embedding?.length !== 384 || 
        action_embedding?.length !== 384 || 
        next_state_embedding?.length !== 384) {
      return NextResponse.json(
        { error: 'Embeddings must be 384-dimensional vectors' },
        { status: 400 }
      );
    }
    
    // Store experience in database
    const { data, error } = await supabase
      .from('experience_replay')
      .insert({
        state_embedding,
        action_embedding,
        next_state_embedding,
        reward,
        metadata
      })
      .select()
      .single();
    
    if (error) {
      console.error('Failed to store experience:', error);
      return NextResponse.json(
        { error: 'Failed to store experience', details: error.message },
        { status: 500 }
      );
    }
    
    // Also update learning stats
    await updateLearningStats(metadata?.modelType || 'General', reward);
    
    return NextResponse.json({
      success: true,
      experienceId: data.id,
      message: 'Experience stored successfully'
    });
    
  } catch (error) {
    console.error('Error in experience storage:', error);
    return NextResponse.json(
      { error: 'Failed to process experience' },
      { status: 500 }
    );
  }
}

// GET: Retrieve learning statistics
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const modelType = searchParams.get('modelType');
    const timeWindow = searchParams.get('timeWindow') || '7 days';
    
    // Try to get learning statistics
    const { data, error } = await supabase.rpc('get_learning_stats', {
      time_window: timeWindow
    });
    
    if (error) {
      console.error('Failed to get learning stats:', error);
      // Return empty stats instead of error to not break the UI
      return NextResponse.json({
        success: true,
        stats: [],
        timeWindow,
        message: 'Learning stats function not deployed yet'
      });
    }
    
    // Filter by model type if specified
    const stats = modelType 
      ? data?.filter((s: any) => s.model_type === modelType)
      : data;
    
    return NextResponse.json({
      success: true,
      stats: stats || [],
      timeWindow
    });
    
  } catch (error) {
    console.error('Error retrieving stats:', error);
    // Return empty stats instead of error
    return NextResponse.json({
      success: true,
      stats: [],
      timeWindow: searchParams.get('timeWindow') || '7 days',
      message: 'Stats temporarily unavailable'
    });
  }
}

// Helper function to update learning statistics
async function updateLearningStats(modelType: string, reward: number) {
  try {
    // This could be expanded to track more sophisticated metrics
    const { data: existing } = await supabase
      .from('model_corrections')
      .select('id')
      .eq('model_type', modelType)
      .single();
    
    if (!existing) {
      // Create initial stats entry
      await supabase
        .from('model_corrections')
        .insert({
          model_type: modelType,
          correction_text: `RL Experience - Reward: ${reward}`,
          feedback_type: reward > 0 ? 'positive' : 'negative',
          patterns: {
            category: 'rl_experience',
            reward: reward.toString()
          }
        });
    }
  } catch (error) {
    console.error('Failed to update learning stats:', error);
  }
}