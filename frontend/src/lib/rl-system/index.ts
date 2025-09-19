// Comprehensive RL System for saving outputs and feedback to Supabase
import { createClient } from '@supabase/supabase-js';

// Initialize Supabase client
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';
const supabase = createClient(supabaseUrl, supabaseAnonKey);

export type OutputFormat = 'docs' | 'deck' | 'spreadsheet' | 'matrix' | 'analysis' | 'markdown';

export interface RLExperience {
  session_id: string;
  prompt: string;
  output_format: OutputFormat;
  output_data: any;
  metadata?: {
    company?: string;
    skills_used?: string[];
    processing_time?: number;
    model_type?: string;
  };
  created_at?: string;
}

export interface RLFeedback {
  experience_id: string;
  session_id: string;
  feedback_type: 'positive' | 'negative' | 'correction' | 'semantic';
  feedback_text?: string;
  corrected_output?: any;
  reward_score?: number;
  created_at?: string;
}

export class UnifiedRLSystem {
  private sessionId: string;
  private outputFormat: OutputFormat;
  
  constructor(outputFormat: OutputFormat = 'docs') {
    this.sessionId = this.generateSessionId();
    this.outputFormat = outputFormat;
  }
  
  private generateSessionId(): string {
    if (typeof window !== 'undefined') {
      return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    }
    return `server-${Date.now()}`;
  }
  
  // Save the agent output to Supabase
  async saveOutput(params: {
    prompt: string;
    output: any;
    outputFormat?: OutputFormat;
    metadata?: any;
  }): Promise<{ success: boolean; experienceId?: string; error?: string }> {
    try {
      const experience: RLExperience = {
        session_id: this.sessionId,
        prompt: params.prompt,
        output_format: params.outputFormat || this.outputFormat,
        output_data: params.output,
        metadata: params.metadata,
        created_at: new Date().toISOString()
      };
      
      const { data, error } = await supabase
        .from('agent_feedback')  // Using existing table
        .insert({
          session_id: experience.session_id,
          prompt: experience.prompt,
          output_format: experience.output_format,
          output_data: experience.output_data,
          metadata: experience.metadata,
          created_at: experience.created_at
        })
        .select()
        .single();
      
      if (error) {
        console.error('Error saving RL experience:', error);
        return { success: false, error: error.message };
      }
      
      console.log('✅ RL Experience saved:', data?.id);
      return { success: true, experienceId: data?.id };
    } catch (error) {
      console.error('Failed to save RL experience:', error);
      return { success: false, error: String(error) };
    }
  }
  
  // Save user feedback about the output
  async saveFeedback(params: {
    experienceId: string;
    feedbackType: 'positive' | 'negative' | 'correction' | 'semantic';
    feedbackText?: string;
    correctedOutput?: any;
    rewardScore?: number;
  }): Promise<{ success: boolean; feedbackId?: string; error?: string }> {
    try {
      const feedback: RLFeedback = {
        experience_id: params.experienceId,
        session_id: this.sessionId,
        feedback_type: params.feedbackType,
        feedback_text: params.feedbackText,
        corrected_output: params.correctedOutput,
        reward_score: params.rewardScore,
        created_at: new Date().toISOString()
      };
      
      const { data, error } = await supabase
        .from('model_feedback')  // Using existing table
        .insert({
          experience_id: feedback.experience_id,
          session_id: feedback.session_id,
          feedback_type: feedback.feedback_type,
          feedback_text: feedback.feedback_text,
          corrected_output: feedback.corrected_output,
          reward_score: feedback.reward_score,
          created_at: feedback.created_at
        })
        .select()
        .single();
      
      if (error) {
        console.error('Error saving RL feedback:', error);
        return { success: false, error: error.message };
      }
      
      console.log('✅ RL Feedback saved:', data?.id);
      return { success: true, feedbackId: data?.id };
    } catch (error) {
      console.error('Failed to save RL feedback:', error);
      return { success: false, error: String(error) };
    }
  }
  
  // Get recent experiences for a specific format
  async getRecentExperiences(
    outputFormat?: OutputFormat,
    limit: number = 10
  ): Promise<RLExperience[]> {
    try {
      let query = supabase
        .from('agent_feedback')  // Using existing table
        .select('*')
        .order('created_at', { ascending: false })
        .limit(limit);
      
      if (outputFormat) {
        query = query.eq('output_format', outputFormat);
      }
      
      const { data, error } = await query;
      
      if (error) {
        console.error('Error fetching experiences:', error);
        return [];
      }
      
      return data || [];
    } catch (error) {
      console.error('Failed to fetch experiences:', error);
      return [];
    }
  }
  
  // Get feedback for specific experiences
  async getFeedbackForExperience(experienceId: string): Promise<RLFeedback[]> {
    try {
      const { data, error } = await supabase
        .from('model_feedback')  // Using existing table
        .select('*')
        .eq('experience_id', experienceId)
        .order('created_at', { ascending: false });
      
      if (error) {
        console.error('Error fetching feedback:', error);
        return [];
      }
      
      return data || [];
    } catch (error) {
      console.error('Failed to fetch feedback:', error);
      return [];
    }
  }
  
  // Get aggregated stats
  async getStats(outputFormat?: OutputFormat): Promise<{
    totalExperiences: number;
    totalFeedback: number;
    avgRewardScore: number;
    positiveFeedbackRate: number;
    formatBreakdown: Record<string, number>;
  }> {
    try {
      // Get experience count
      let experienceQuery = supabase
        .from('agent_feedback')  // Using existing table
        .select('*, model_feedback(reward_score, feedback_type)', { count: 'exact' });
      
      if (outputFormat) {
        experienceQuery = experienceQuery.eq('output_format', outputFormat);
      }
      
      const { data: experiences, count } = await experienceQuery;
      
      // Calculate stats
      let totalFeedback = 0;
      let totalReward = 0;
      let positiveFeedback = 0;
      const formatCounts: Record<string, number> = {};
      
      experiences?.forEach((exp: any) => {
        // Count by format
        formatCounts[exp.output_format] = (formatCounts[exp.output_format] || 0) + 1;
        
        // Process feedback
        if (exp.model_feedback && Array.isArray(exp.model_feedback)) {
          exp.model_feedback.forEach((fb: any) => {
            totalFeedback++;
            if (fb.reward_score) {
              totalReward += fb.reward_score;
            }
            if (fb.feedback_type === 'positive') {
              positiveFeedback++;
            }
          });
        }
      });
      
      return {
        totalExperiences: count || 0,
        totalFeedback,
        avgRewardScore: totalFeedback > 0 ? totalReward / totalFeedback : 0,
        positiveFeedbackRate: totalFeedback > 0 ? positiveFeedback / totalFeedback : 0,
        formatBreakdown: formatCounts
      };
    } catch (error) {
      console.error('Failed to get stats:', error);
      return {
        totalExperiences: 0,
        totalFeedback: 0,
        avgRewardScore: 0,
        positiveFeedbackRate: 0,
        formatBreakdown: {}
      };
    }
  }
}

// Legacy SpreadsheetRLSystem for backward compatibility
export class SpreadsheetRLSystem {
  private rlSystem: UnifiedRLSystem;
  private config: any;
  private epsilon: number;
  private lastExperienceId?: string;
  
  constructor(config?: {
    modelType?: string;
    company?: string;
    epsilon?: number;
    temperature?: number;
    autoLearn?: boolean;
  }) {
    this.config = config || {};
    this.epsilon = config?.epsilon || 0.1;
    this.rlSystem = new UnifiedRLSystem('spreadsheet');
  }
  
  async initialize() {
    console.log('SpreadsheetRLSystem initialized');
    return Promise.resolve();
  }
  
  async storeExperience(params: {
    prompt: string;
    action: string;
    state_before: any;
    state_after: any;
    reward: number;
    session_id?: string;
    company?: string;
  }) {
    const result = await this.rlSystem.saveOutput({
      prompt: params.prompt,
      output: {
        action: params.action,
        state_after: params.state_after
      },
      metadata: {
        company: params.company,
        model_type: this.config.modelType,
        state_before: params.state_before,
        reward: params.reward
      }
    });
    
    if (result.experienceId) {
      this.lastExperienceId = result.experienceId;
    }
    
    return result;
  }
  
  async getSuggestion(currentGrid: any, prompt: string) {
    // TODO: Implement ML-based suggestion using historical data
    const recentExperiences = await this.rlSystem.getRecentExperiences('spreadsheet', 5);
    console.log('Recent similar experiences:', recentExperiences.length);
    return { action: null, confidence: 0 };
  }
  
  async recordFeedback(reward: number | string, gridAPI: any, specificFeedback?: string) {
    if (!this.lastExperienceId) {
      console.warn('No experience ID to attach feedback to');
      return { success: false };
    }
    
    const feedbackType = typeof reward === 'number' 
      ? (reward > 0 ? 'positive' : 'negative')
      : 'semantic';
    
    return await this.rlSystem.saveFeedback({
      experienceId: this.lastExperienceId,
      feedbackType,
      feedbackText: specificFeedback || String(reward),
      rewardScore: typeof reward === 'number' ? reward : undefined
    });
  }
  
  decayEpsilon() {
    this.epsilon = Math.max(0.01, this.epsilon * 0.995);
    console.log('Epsilon decayed to:', this.epsilon);
  }
  
  async getStats() {
    const stats = await this.rlSystem.getStats('spreadsheet');
    return {
      total_experiences: stats.totalExperiences,
      average_reward: stats.avgRewardScore,
      companies_tracked: Object.keys(stats.formatBreakdown).length,
      session: {
        avgReward: stats.avgRewardScore,
        bufferSize: stats.totalExperiences,
        lastReward: 0
      },
      agent: {
        epsilon: this.epsilon
      }
    };
  }
}

// Export the main RL system for use in other components
export default UnifiedRLSystem;