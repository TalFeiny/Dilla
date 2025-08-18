/**
 * Central RL Coordinator
 * Manages system-wide reinforcement learning across all agents
 */

import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export interface RLState {
  query: string;
  agent: string;
  context: any;
  timestamp: number;
}

export interface RLAction {
  type: string;
  parameters: any;
  agent: string;
}

export interface RLExperience {
  sessionId: string;
  state: RLState;
  action: RLAction;
  reward: number;
  nextState: RLState;
  feedback?: string;
  corrections?: any;
}

class RLCoordinator {
  private static instance: RLCoordinator;
  private experienceBuffer: RLExperience[] = [];
  private learningRate = 0.1;
  private explorationRate = 0.2;
  
  private constructor() {
    // Load historical experiences on init
    this.loadHistoricalExperiences();
  }
  
  static getInstance(): RLCoordinator {
    if (!RLCoordinator.instance) {
      RLCoordinator.instance = new RLCoordinator();
    }
    return RLCoordinator.instance;
  }
  
  /**
   * Before any agent processes a query, check RL for learned patterns
   */
  async preprocessQuery(query: string, agent: string, context: any): Promise<{
    enhancedContext: any;
    suggestedActions: RLAction[];
    confidence: number;
  }> {
    console.log(`🧠 RL preprocessing for ${agent}: ${query.substring(0, 50)}...`);
    
    // Find similar past experiences
    const similarExperiences = await this.findSimilarExperiences(query, agent);
    
    if (similarExperiences.length === 0) {
      return {
        enhancedContext: context,
        suggestedActions: [],
        confidence: 0
      };
    }
    
    // Extract successful patterns (high reward experiences)
    const successfulPatterns = similarExperiences
      .filter(exp => exp.reward > 0.7)
      .sort((a, b) => b.reward - a.reward);
    
    // Build enhanced context from learned patterns
    const enhancedContext = {
      ...context,
      rlPatterns: successfulPatterns.map(exp => ({
        action: exp.action,
        reward: exp.reward,
        feedback: exp.feedback
      })),
      learnedCorrections: await this.getLearnedCorrections(query),
      historicalSuccess: this.calculateHistoricalSuccess(similarExperiences)
    };
    
    // Suggest actions based on successful patterns
    const suggestedActions = this.extractSuggestedActions(successfulPatterns);
    
    // Calculate confidence based on experience quantity and quality
    const confidence = this.calculateConfidence(similarExperiences);
    
    console.log(`📊 RL found ${similarExperiences.length} similar experiences, confidence: ${confidence}`);
    
    return {
      enhancedContext,
      suggestedActions,
      confidence
    };
  }
  
  /**
   * After agent completes, store the experience
   */
  async recordExperience(
    sessionId: string,
    state: RLState,
    action: RLAction,
    result: any,
    initialReward?: number
  ): Promise<void> {
    const experience: RLExperience = {
      sessionId,
      state,
      action,
      reward: initialReward || 0.5, // Neutral initial reward
      nextState: {
        ...state,
        timestamp: Date.now()
      }
    };
    
    // Add to buffer
    this.experienceBuffer.push(experience);
    
    // Store in database
    try {
      await supabase.from('rl_experiences').insert({
        session_id: sessionId,
        agent: action.agent,
        state: state,
        action: action,
        reward: experience.reward,
        next_state: experience.nextState,
        created_at: new Date().toISOString()
      });
    } catch (error) {
      console.error('Failed to store RL experience:', error);
    }
    
    // Trigger learning if buffer is large enough
    if (this.experienceBuffer.length >= 10) {
      await this.learn();
    }
  }
  
  /**
   * Update reward based on user feedback
   */
  async updateReward(
    sessionId: string,
    feedback: string,
    score: number,
    corrections?: any
  ): Promise<void> {
    console.log(`📝 RL feedback received: ${feedback}, score: ${score}`);
    
    // Find the experience in buffer or database
    const experience = this.experienceBuffer.find(exp => exp.sessionId === sessionId);
    
    if (experience) {
      // Update reward based on feedback
      experience.reward = this.calculateRewardFromFeedback(score, feedback);
      experience.feedback = feedback;
      experience.corrections = corrections;
      
      // Parse corrections for specific learning
      if (corrections) {
        await this.learnFromCorrections(experience, corrections);
      }
      
      // Update in database
      await supabase
        .from('rl_experiences')
        .update({
          reward: experience.reward,
          feedback: feedback,
          corrections: corrections
        })
        .eq('session_id', sessionId);
    }
    
    // Store feedback patterns
    if (corrections) {
      await this.storeCorrectionsPattern(feedback, corrections, sessionId);
    }
  }
  
  /**
   * Learn from corrections
   */
  private async learnFromCorrections(experience: RLExperience, corrections: any): Promise<void> {
    // Extract patterns from corrections
    const patterns = this.extractPatternsFromCorrections(corrections);
    
    // Store learned patterns
    for (const pattern of patterns) {
      await supabase.from('rl_learned_patterns').insert({
        pattern_type: pattern.type,
        pattern_data: pattern.data,
        agent: experience.action.agent,
        confidence: pattern.confidence,
        created_at: new Date().toISOString()
      });
    }
  }
  
  /**
   * Find similar past experiences
   */
  private async findSimilarExperiences(query: string, agent: string): Promise<RLExperience[]> {
    // Use embeddings for similarity search
    const { data: similar } = await supabase
      .from('rl_experiences')
      .select('*')
      .eq('agent', agent)
      .order('created_at', { ascending: false })
      .limit(20);
    
    if (!similar) return [];
    
    // Filter by query similarity (simple keyword matching for now)
    const keywords = query.toLowerCase().split(' ');
    return similar
      .filter((exp: any) => {
        const expKeywords = exp.state?.query?.toLowerCase().split(' ') || [];
        const overlap = keywords.filter(k => expKeywords.includes(k)).length;
        return overlap > keywords.length * 0.3; // 30% overlap threshold
      })
      .map((exp: any) => ({
        sessionId: exp.session_id,
        state: exp.state,
        action: exp.action,
        reward: exp.reward,
        nextState: exp.next_state,
        feedback: exp.feedback,
        corrections: exp.corrections
      }));
  }
  
  /**
   * Get learned corrections for a query
   */
  private async getLearnedCorrections(query: string): Promise<any[]> {
    const { data: corrections } = await supabase
      .from('rl_corrections')
      .select('*')
      .order('created_at', { ascending: false })
      .limit(10);
    
    return corrections || [];
  }
  
  /**
   * Calculate historical success rate
   */
  private calculateHistoricalSuccess(experiences: RLExperience[]): number {
    if (experiences.length === 0) return 0;
    const avgReward = experiences.reduce((sum, exp) => sum + exp.reward, 0) / experiences.length;
    return Math.min(1, avgReward);
  }
  
  /**
   * Extract suggested actions from successful patterns
   */
  private extractSuggestedActions(patterns: RLExperience[]): RLAction[] {
    const actions: RLAction[] = [];
    const seen = new Set<string>();
    
    for (const pattern of patterns) {
      const actionKey = `${pattern.action.type}-${JSON.stringify(pattern.action.parameters)}`;
      if (!seen.has(actionKey)) {
        seen.add(actionKey);
        actions.push(pattern.action);
      }
    }
    
    return actions.slice(0, 5); // Top 5 suggestions
  }
  
  /**
   * Calculate confidence score
   */
  private calculateConfidence(experiences: RLExperience[]): number {
    if (experiences.length === 0) return 0;
    
    // Factors: quantity, recency, reward consistency
    const quantity = Math.min(1, experiences.length / 10);
    const avgReward = experiences.reduce((sum, exp) => sum + exp.reward, 0) / experiences.length;
    const recency = experiences.filter(exp => 
      Date.now() - exp.state.timestamp < 7 * 24 * 60 * 60 * 1000 // Within 7 days
    ).length / experiences.length;
    
    return (quantity * 0.3 + avgReward * 0.5 + recency * 0.2);
  }
  
  /**
   * Calculate reward from feedback
   */
  private calculateRewardFromFeedback(score: number, feedback: string): number {
    // Map feedback to reward
    const feedbackMap: Record<string, number> = {
      'approve': 1.0,
      'good': 0.8,
      'okay': 0.5,
      'needs_edit': 0.3,
      'wrong': -0.5,
      'fix_required': -0.3
    };
    
    // Check feedback text for patterns
    const lowerFeedback = feedback.toLowerCase();
    for (const [key, reward] of Object.entries(feedbackMap)) {
      if (lowerFeedback.includes(key)) {
        return reward;
      }
    }
    
    // Default to score
    return Math.max(-1, Math.min(1, score));
  }
  
  /**
   * Extract patterns from corrections
   */
  private extractPatternsFromCorrections(corrections: any): any[] {
    const patterns = [];
    
    // Check for numerical corrections
    const numberPattern = /should be (\d+(?:\.\d+)?)/gi;
    const matches = corrections.match(numberPattern);
    if (matches) {
      patterns.push({
        type: 'numerical_correction',
        data: { corrections: matches },
        confidence: 0.9
      });
    }
    
    // Check for entity corrections
    if (corrections.includes('not') || corrections.includes('actually')) {
      patterns.push({
        type: 'factual_correction',
        data: { correction: corrections },
        confidence: 0.85
      });
    }
    
    return patterns;
  }
  
  /**
   * Store corrections pattern
   */
  private async storeCorrectionsPattern(feedback: string, corrections: any, sessionId: string): Promise<void> {
    await supabase.from('rl_corrections').insert({
      session_id: sessionId,
      feedback: feedback,
      corrections: corrections,
      created_at: new Date().toISOString()
    });
  }
  
  /**
   * Load historical experiences on startup
   */
  private async loadHistoricalExperiences(): Promise<void> {
    const { data: experiences } = await supabase
      .from('rl_experiences')
      .select('*')
      .gte('reward', 0.7) // Only load successful experiences
      .order('created_at', { ascending: false })
      .limit(100);
    
    if (experiences) {
      console.log(`📚 Loaded ${experiences.length} historical RL experiences`);
    }
  }
  
  /**
   * Perform learning update
   */
  private async learn(): Promise<void> {
    console.log('🎓 RL learning from buffer...');
    
    // Implement experience replay and policy update
    // This would involve updating the model weights based on experiences
    
    // Clear old experiences from buffer
    this.experienceBuffer = this.experienceBuffer.slice(-50); // Keep last 50
  }
  
  /**
   * Get exploration rate (epsilon for epsilon-greedy)
   */
  getExplorationRate(): number {
    // Decay exploration over time
    return Math.max(0.1, this.explorationRate * 0.995);
  }
}

// Export singleton instance
export const rlCoordinator = RLCoordinator.getInstance();