/**
 * Deep RL Integration for Spreadsheet Agent
 * Connects the PPO model to the existing spreadsheet system
 */

import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

interface SpreadsheetAction {
  type: string;
  row: number;
  col: number;
  value?: any;
  formula?: string;
  params?: Record<string, any>;
}

interface GridState {
  grid: any[][];
  metadata: {
    company?: string;
    context?: string;
    lastAction?: SpreadsheetAction;
  };
}

interface RLFeedback {
  reward: number;
  components?: {
    correctness: number;
    efficiency: number;
    consistency: number;
    completeness: number;
    formatting: number;
    complexity: number;
  };
  userFeedback?: 'perfect' | 'good' | 'okay' | 'poor' | 'wrong';
  correction?: string;
}

export class SpreadsheetRLAgent {
  private apiEndpoint = '/api/rl-agent';
  private useDeepRL = false;
  private episodeHistory: any[] = [];
  private currentEpisodeReward = 0;
  
  constructor() {
    this.checkRLAvailability();
  }
  
  /**
   * Check if deep RL model is available
   */
  private async checkRLAvailability() {
    try {
      const response = await fetch(this.apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'status' })
      });
      
      if (response.ok) {
        const status = await response.json();
        this.useDeepRL = status.ready;
        console.log('Deep RL status:', status);
      }
    } catch (error) {
      console.log('Deep RL not available, using traditional approach');
      this.useDeepRL = false;
    }
  }
  
  /**
   * Get next action from RL model or fallback
   */
  async getNextAction(state: GridState): Promise<SpreadsheetAction> {
    if (!this.useDeepRL) {
      return this.getFallbackAction(state);
    }
    
    try {
      const response = await fetch(this.apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'predict',
          state: state
        })
      });
      
      if (!response.ok) {
        return this.getFallbackAction(state);
      }
      
      const result = await response.json();
      
      // Store for learning
      this.episodeHistory.push({
        state: state,
        action: result.action,
        timestamp: Date.now()
      });
      
      return result.action;
      
    } catch (error) {
      console.error('RL prediction failed:', error);
      return this.getFallbackAction(state);
    }
  }
  
  /**
   * Send feedback to RL model for learning
   */
  async provideFeedback(
    stateBefore: GridState,
    action: SpreadsheetAction,
    stateAfter: GridState,
    feedback: RLFeedback
  ): Promise<void> {
    if (!this.useDeepRL) {
      // Store in Q-table for basic learning
      await this.storeBasicLearning(stateBefore, action, feedback);
      return;
    }
    
    try {
      const response = await fetch(this.apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'train',
          state: {
            before: stateBefore,
            action: action,
            after: stateAfter,
            done: false
          },
          feedback: feedback
        })
      });
      
      if (response.ok) {
        const stats = await response.json();
        this.currentEpisodeReward += feedback.reward;
        console.log('RL training stats:', stats);
      }
      
    } catch (error) {
      console.error('RL training failed:', error);
      // Fallback to basic learning
      await this.storeBasicLearning(stateBefore, action, feedback);
    }
  }
  
  /**
   * Process user correction and learn from it
   */
  async learnFromCorrection(
    state: GridState,
    correction: string,
    actualValue: any
  ): Promise<void> {
    // Parse the correction semantically
    const pattern = this.parseCorrection(correction);
    
    // Create strong negative/positive feedback
    const feedback: RLFeedback = {
      reward: pattern.isCorrect ? 1.0 : -1.0,
      components: {
        correctness: pattern.isCorrect ? 1.0 : 0.0,
        efficiency: 0.5,
        consistency: 0.5,
        completeness: 0.5,
        formatting: 0.5,
        complexity: 0.5
      },
      correction: correction
    };
    
    // Send to RL model
    if (this.useDeepRL) {
      await this.provideFeedback(
        state,
        { type: 'correction', row: 0, col: 0, value: actualValue },
        state,
        feedback
      );
    }
    
    // Store correction pattern for retrieval
    await this.storeCorrectionPattern(state, correction, actualValue);
  }
  
  /**
   * End episode and finalize learning
   */
  async endEpisode(success: boolean): Promise<void> {
    if (!this.useDeepRL || this.episodeHistory.length === 0) {
      return;
    }
    
    // Mark last state as done
    const lastEntry = this.episodeHistory[this.episodeHistory.length - 1];
    
    try {
      await fetch(this.apiEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'train',
          state: {
            before: lastEntry.state,
            action: lastEntry.action,
            after: lastEntry.state,
            done: true
          },
          feedback: {
            reward: success ? 10.0 : -5.0
          }
        })
      });
      
      console.log(`Episode ended. Total reward: ${this.currentEpisodeReward}`);
      
    } catch (error) {
      console.error('Failed to end episode:', error);
    }
    
    // Reset for next episode
    this.episodeHistory = [];
    this.currentEpisodeReward = 0;
  }
  
  /**
   * Fallback action when RL is not available
   */
  private async getFallbackAction(state: GridState): Promise<SpreadsheetAction> {
    // Use existing Q-table or rule-based approach
    const { data: experiences } = await supabase
      .from('rl_experience_replay')
      .select('*')
      .eq('state_hash', this.hashState(state))
      .order('reward', { ascending: false })
      .limit(1);
    
    if (experiences && experiences.length > 0) {
      return JSON.parse(experiences[0].action);
    }
    
    // Default action
    return {
      type: 'set_value',
      row: 0,
      col: 0,
      value: 0
    };
  }
  
  /**
   * Store basic learning in Q-table
   */
  private async storeBasicLearning(
    state: GridState,
    action: SpreadsheetAction,
    feedback: RLFeedback
  ): Promise<void> {
    await supabase.from('rl_experience_replay').insert({
      state_hash: this.hashState(state),
      state: state,
      action: action,
      reward: feedback.reward,
      metadata: {
        components: feedback.components,
        userFeedback: feedback.userFeedback,
        correction: feedback.correction
      }
    });
  }
  
  /**
   * Store correction pattern for future retrieval
   */
  private async storeCorrectionPattern(
    state: GridState,
    correction: string,
    actualValue: any
  ): Promise<void> {
    await supabase.from('spreadsheet_corrections').insert({
      state_context: this.extractContext(state),
      correction_text: correction,
      actual_value: actualValue,
      pattern: this.parseCorrection(correction),
      created_at: new Date()
    });
  }
  
  /**
   * Parse user correction into pattern
   */
  private parseCorrection(correction: string): any {
    const patterns = {
      revenue: /revenue\s+should\s+be\s+([\d.]+[MBK]?)/i,
      growth: /growth\s+rate\s+should\s+be\s+([\d.]+%?)/i,
      formula: /use\s+formula\s+(.+)/i,
      value: /should\s+be\s+([\d.]+)/i
    };
    
    for (const [type, regex] of Object.entries(patterns)) {
      const match = correction.match(regex);
      if (match) {
        return {
          type,
          value: match[1],
          isCorrect: false
        };
      }
    }
    
    return {
      type: 'general',
      value: correction,
      isCorrect: false
    };
  }
  
  /**
   * Hash state for storage
   */
  private hashState(state: GridState): string {
    const simplified = {
      shape: [state.grid.length, state.grid[0]?.length || 0],
      nonEmpty: state.grid.flat().filter(cell => cell).length,
      context: state.metadata.context || ''
    };
    return btoa(JSON.stringify(simplified));
  }
  
  /**
   * Extract context from state
   */
  private extractContext(state: GridState): any {
    return {
      company: state.metadata.company,
      gridShape: [state.grid.length, state.grid[0]?.length || 0],
      hasFormulas: state.grid.flat().some(cell => 
        typeof cell === 'string' && cell.startsWith('=')
      ),
      lastAction: state.metadata.lastAction
    };
  }
  
  /**
   * Get learning statistics
   */
  async getStats(): Promise<any> {
    if (this.useDeepRL) {
      try {
        const response = await fetch(this.apiEndpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'status' })
        });
        
        if (response.ok) {
          return await response.json();
        }
      } catch (error) {
        console.error('Failed to get RL stats:', error);
      }
    }
    
    // Fallback stats from database
    const { data: experiences } = await supabase
      .from('rl_experience_replay')
      .select('reward')
      .order('created_at', { ascending: false })
      .limit(100);
    
    if (experiences) {
      const rewards = experiences.map(e => e.reward);
      return {
        avgReward: rewards.reduce((a, b) => a + b, 0) / rewards.length,
        maxReward: Math.max(...rewards),
        minReward: Math.min(...rewards),
        totalExperiences: experiences.length,
        useDeepRL: this.useDeepRL
      };
    }
    
    return {
      avgReward: 0,
      maxReward: 0,
      minReward: 0,
      totalExperiences: 0,
      useDeepRL: false
    };
  }
}

// Export singleton instance
export const spreadsheetRLAgent = new SpreadsheetRLAgent();