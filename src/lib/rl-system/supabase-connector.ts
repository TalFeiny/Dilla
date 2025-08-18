// Bridge between frontend RL system and Supabase functions
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

export class RLSupabaseConnector {
  // Store experience using SQL function
  async storeExperience(
    state: string,
    action: string,
    nextState: string,
    reward: number,
    metadata: any
  ) {
    try {
      // First try the SQL function
      const { data, error } = await supabase.rpc('store_rl_experience', {
        state_text: state,
        action_text: action,
        next_state_text: nextState,
        reward_value: reward,
        meta_data: metadata
      });

      if (error) {
        // If function doesn't exist, log but don't throw
        if (error.message?.includes('function') || error.message?.includes('does not exist')) {
          console.warn('RL functions not deployed yet. Run scripts/fix_rl_functions.sql in Supabase');
          return null;
        }
        throw error;
      }
      return data;
    } catch (error) {
      console.error('Failed to store RL experience:', error);
      // Return null instead of throwing to prevent UI breakage
      return null;
    }
  }

  // Find similar past experiences
  async findSimilarExperiences(
    currentState: string,
    minSimilarity: number = 0.7,
    limit: number = 5
  ) {
    try {
      // Generate embedding for current state
      const { data: embedding, error: embedError } = await supabase.rpc('embed_rl_feedback', {
        input_text: currentState,
        context_type: 'grid_state'
      });

      if (embedError) {
        console.warn('Embedding function not available:', embedError.message);
        return [];
      }

      // Find matches
      const { data, error } = await supabase.rpc('match_experiences', {
        query_embedding: embedding,
        match_threshold: minSimilarity,
        match_count: limit
      });

      if (error) {
        console.warn('Match function not available:', error.message);
        return [];
      }
      return data || [];
    } catch (error) {
      console.error('Failed to find similar experiences:', error);
      return [];
    }
  }

  // Get best actions for current state
  async getBestActions(currentState: string, minReward: number = 0.5) {
    try {
      const { data: embedding, error: embedError } = await supabase.rpc('embed_rl_feedback', {
        input_text: currentState,
        context_type: 'grid_state'
      });

      if (embedError) {
        console.warn('Embedding function not available:', embedError.message);
        return [];
      }

      const { data, error } = await supabase.rpc('get_best_actions', {
        query_embedding: embedding,
        min_reward: minReward,
        match_count: 5
      });

      if (error) {
        console.warn('Best actions function not available:', error.message);
        return [];
      }
      return data || [];
    } catch (error) {
      console.error('Failed to get best actions:', error);
      return [];
    }
  }

  // Get learning statistics
  async getLearningStats(timeWindow: string = '7 days') {
    try {
      // Use a simpler query that doesn't cause SQL errors
      const { data, error } = await supabase
        .from('experience_replay')
        .select('metadata, reward, created_at')
        .gte('created_at', new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString());

      if (error) {
        console.warn('Learning stats query failed:', error.message);
        return [];
      }

      // Process the data to get stats
      const stats = new Map();
      
      (data || []).forEach(item => {
        const modelType = item.metadata?.model_type || 'General';
        if (!stats.has(modelType)) {
          stats.set(modelType, {
            model_type: modelType,
            total_experiences: 0,
            total_reward: 0,
            success_count: 0
          });
        }
        
        const stat = stats.get(modelType);
        stat.total_experiences++;
        stat.total_reward += item.reward || 0;
        if (item.reward > 0) stat.success_count++;
      });

      return Array.from(stats.values()).map(stat => ({
        model_type: stat.model_type,
        total_experiences: stat.total_experiences,
        avg_reward: stat.total_experiences > 0 ? Math.round((stat.total_reward / stat.total_experiences) * 1000) / 1000 : 0,
        success_rate: stat.total_experiences > 0 ? Math.round((stat.success_count / stat.total_experiences) * 1000) / 1000 : 0,
        improvement_trend: 0
      }));
    } catch (error) {
      console.error('Failed to get learning stats:', error);
      return [];
    }
  }
}

// Create SQL function to handle the full flow
export const RL_STORE_FUNCTION = `
CREATE OR REPLACE FUNCTION store_rl_experience(
  state_text TEXT,
  action_text TEXT,
  next_state_text TEXT,
  reward_value FLOAT,
  meta_data JSONB DEFAULT '{}'
)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
  experience_id INT;
BEGIN
  INSERT INTO experience_replay (
    state_embedding,
    action_embedding,
    next_state_embedding,
    reward,
    metadata
  ) VALUES (
    embed_rl_feedback(state_text, 'grid_state'),
    embed_rl_feedback(action_text, 'action'),
    embed_rl_feedback(next_state_text, 'grid_state'),
    reward_value,
    meta_data
  ) RETURNING id INTO experience_id;
  
  RETURN experience_id;
END;
$$;`;