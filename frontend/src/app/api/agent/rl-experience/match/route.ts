import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

// POST: Find similar experiences
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      embedding,
      modelType,
      minReward = 0.5,
      limit = 10,
      threshold = 0.7
    } = body;
    
    // Validate embedding dimension
    if (!embedding || embedding.length !== 384) {
      return NextResponse.json(
        { error: 'Embedding must be a 384-dimensional vector' },
        { status: 400 }
      );
    }
    
    // Query similar experiences using pgvector
    const { data, error } = await supabase.rpc('match_experiences', {
      query_embedding: embedding,
      match_threshold: threshold,
      match_count: limit,
      model_type: modelType
    });
    
    if (error) {
      console.error('Failed to match experiences:', error);
      // Return empty results instead of error to prevent UI breaking
      return NextResponse.json({
        success: true,
        experiences: [],
        bestActions: [],
        totalMatches: 0,
        filteredCount: 0,
        message: 'Experience matching not yet deployed'
      });
    }
    
    // Filter by minimum reward
    const filteredExperiences = data?.filter((exp: any) => exp.reward >= minReward) || [];
    
    // Get best actions for this state  
    const { data: bestActions, error: bestActionsError } = await supabase.rpc('get_best_actions', {
      query_embedding: embedding,
      min_reward: minReward,
      match_count: 5
    });
    
    if (bestActionsError) {
      console.error('Failed to get best actions:', bestActionsError);
    }
    
    return NextResponse.json({
      success: true,
      experiences: filteredExperiences,
      bestActions: bestActions || [],
      totalMatches: data?.length || 0,
      filteredCount: filteredExperiences.length
    });
    
  } catch (error) {
    console.error('Error matching experiences:', error);
    return NextResponse.json(
      { error: 'Failed to match experiences' },
      { status: 500 }
    );
  }
}

// GET: Get best actions for a state (without embedding)
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const modelType = searchParams.get('modelType');
    const limit = parseInt(searchParams.get('limit') || '10');
    
    // Get top performing actions
    const query = supabase
      .from('experience_replay')
      .select('metadata, reward')
      .gte('reward', 0.7)
      .order('reward', { ascending: false })
      .limit(limit);
    
    if (modelType) {
      query.eq('metadata->model_type', modelType);
    }
    
    const { data, error } = await query;
    
    if (error) {
      console.error('Failed to get best actions:', error);
      return NextResponse.json(
        { error: 'Failed to retrieve best actions' },
        { status: 500 }
      );
    }
    
    // Group by action type and calculate average rewards
    const actionStats = data?.reduce((acc: any, exp: any) => {
      const actionType = exp.metadata?.actionType || 'unknown';
      if (!acc[actionType]) {
        acc[actionType] = { count: 0, totalReward: 0, examples: [] };
      }
      acc[actionType].count++;
      acc[actionType].totalReward += exp.reward;
      if (acc[actionType].examples.length < 3) {
        acc[actionType].examples.push(exp.metadata?.actionText);
      }
      return acc;
    }, {});
    
    // Calculate averages
    const actionSummary = Object.entries(actionStats || {}).map(([type, stats]: [string, any]) => ({
      actionType: type,
      avgReward: stats.totalReward / stats.count,
      count: stats.count,
      examples: stats.examples
    })).sort((a, b) => b.avgReward - a.avgReward);
    
    return NextResponse.json({
      success: true,
      topActions: data?.slice(0, 5).map((exp: any) => ({
        action: exp.metadata?.actionText,
        reward: exp.reward,
        type: exp.metadata?.actionType
      })),
      actionSummary
    });
    
  } catch (error) {
    console.error('Error getting best actions:', error);
    return NextResponse.json(
      { error: 'Failed to retrieve best actions' },
      { status: 500 }
    );
  }
}