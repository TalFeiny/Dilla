'use client';

import { SimpleEmbeddings as LocalEmbeddings } from './simple-embeddings';
import { ExperienceCollector, Experience } from './experience-collector';
import { RAGPolicyAgent, PolicyAction } from './policy-agent';
import { RewardCalculator, RewardBreakdown } from './reward-calculator';
import { SemanticFeedbackParser, SemanticFeedback } from './semantic-feedback';

export interface RLSystemConfig {
  modelType?: string;
  company?: string;
  epsilon?: number;
  temperature?: number;
  autoLearn?: boolean;
}

export class SpreadsheetRLSystem {
  private embeddings: LocalEmbeddings;
  private collector: ExperienceCollector;
  private agent: RAGPolicyAgent;
  private rewardCalculator: RewardCalculator;
  private feedbackParser: SemanticFeedbackParser;
  private config: RLSystemConfig;
  private isInitialized: boolean = false;
  private currentSessionId: string;
  private previousState: Record<string, any> | null = null;
  private previousAction: string | null = null;
  private lastRewardBreakdown: RewardBreakdown | null = null;
  private performanceHistory: number[] = [];
  private successRate: number = 0;
  
  constructor(config: RLSystemConfig = {}) {
    this.embeddings = LocalEmbeddings.getInstance();
    this.collector = new ExperienceCollector();
    this.agent = new RAGPolicyAgent();
    this.rewardCalculator = new RewardCalculator();
    this.feedbackParser = new SemanticFeedbackParser();
    this.config = {
      epsilon: 0.3,  // Start with higher exploration
      temperature: 1.0,
      autoLearn: true,
      ...config
    };
    this.currentSessionId = this.generateSessionId();
    
    // Configure agent with adaptive parameters
    if (config.epsilon !== undefined) {
      this.agent.setEpsilon(config.epsilon);
    }
    if (config.temperature !== undefined) {
      this.agent.setTemperature(config.temperature);
    }
    
    // Initialize performance tracking
    this.performanceHistory = [];
    this.successRate = 0;
  }
  
  async initialize() {
    if (this.isInitialized) return;
    
    console.log('Initializing RL System...');
    
    // Initialize embeddings model
    await this.embeddings.initialize();
    
    // Load saved policy if available
    await this.agent.loadModel();
    
    this.isInitialized = true;
    console.log('RL System initialized');
  }
  
  // Main method: Execute action with learning
  async executeWithLearning(
    command: string,
    gridAPI: any,
    userIntent?: string
  ): Promise<{
    executed: boolean;
    action: PolicyAction;
    waitingForFeedback: boolean;
    automaticReward?: RewardBreakdown;
  }> {
    await this.initialize();
    
    // Capture state before action
    const stateBefore = gridAPI.getState();
    this.previousState = stateBefore;
    this.previousAction = command;
    
    // Get AI suggestion based on current state
    const suggestedAction = await this.agent.selectAction(
      stateBefore,
      userIntent || command,
      this.config.modelType
    );
    
    // Execute the command (either suggested or user's)
    let executedCommand = command;
    let learningApplied = false;
    if (suggestedAction.source === 'retrieval' && suggestedAction.confidence > 0.7) {
      // Use suggested action if it's from retrieval and high confidence
      executedCommand = suggestedAction.action;
      learningApplied = true;
      console.log(`🧠 USING LEARNED EXPERIENCE: ${executedCommand}`);
      console.log(`📊 Confidence: ${(suggestedAction.confidence * 100).toFixed(0)}%`);
      console.log(`🔍 Based on similar past success`);
    }
    
    // Execute on grid
    try {
      eval(executedCommand);
    } catch (error) {
      console.error('Failed to execute command:', error);
      return {
        executed: false,
        action: suggestedAction,
        waitingForFeedback: false
      };
    }
    
    // Calculate automatic reward immediately
    const stateAfter = gridAPI.getState();
    const automaticReward = this.rewardCalculator.calculateAutomaticReward(
      stateBefore,
      stateAfter,
      executedCommand,
      userIntent || command,
      this.config.modelType
    );
    
    this.lastRewardBreakdown = automaticReward;
    
    // If automatic reward is high confidence and very good/bad, auto-learn
    if (automaticReward.confidence > 0.8 && Math.abs(automaticReward.totalReward) > 0.7) {
      await this.recordFeedback(automaticReward.totalReward, gridAPI, 'automatic evaluation');
    }
    
    // Adaptive epsilon decay based on performance
    this.updateExplorationRate(automaticReward.totalReward);
    
    return {
      executed: true,
      action: suggestedAction,
      waitingForFeedback: true,
      automaticReward,
      learningApplied,
      learningSummary: learningApplied 
        ? `Used past successful pattern with ${(suggestedAction.confidence * 100).toFixed(0)}% confidence`
        : null
    };
  }
  
  // Record feedback and learn - now handles both numeric and semantic
  async recordFeedback(
    rewardOrFeedback: number | string,
    gridAPI: any,
    specificFeedback?: string
  ) {
    let finalReward: number;
    let feedbackMetadata: any = {};
    
    // Handle semantic feedback
    if (typeof rewardOrFeedback === 'string') {
      const semantic = this.feedbackParser.parseFeedback(
        rewardOrFeedback,
        this.previousState
      );
      
      // If we can apply the correction, do it
      if (semantic.suggestedAction && gridAPI) {
        try {
          eval(semantic.suggestedAction);
          console.log('Applied semantic correction:', semantic.suggestedAction);
        } catch (e) {
          console.error('Failed to apply correction:', e);
        }
      }
      
      // Use semantic reward combined with automatic
      if (this.lastRewardBreakdown) {
        finalReward = this.rewardCalculator.combineRewards(
          this.lastRewardBreakdown,
          { score: semantic.reward, confidence: semantic.confidence }
        );
      } else {
        finalReward = semantic.reward;
      }
      
      feedbackMetadata = {
        semantic: semantic,
        rawFeedback: rewardOrFeedback
      };
      specificFeedback = rewardOrFeedback;
    } else {
      // Numeric reward - combine with automatic if available
      if (this.lastRewardBreakdown) {
        finalReward = this.rewardCalculator.combineRewards(
          this.lastRewardBreakdown,
          { score: rewardOrFeedback, confidence: 0.9 } // High confidence for explicit human feedback
        );
      } else {
        finalReward = rewardOrFeedback;
      }
    }
    if (!this.previousState || !this.previousAction) {
      console.warn('No previous state/action to learn from');
      return;
    }
    
    // Capture state after action
    const stateAfter = gridAPI.getState();
    
    // Collect experience with enhanced metadata
    const experience = await this.collector.collectExperience(
      this.previousState,
      this.previousAction,
      stateAfter,
      finalReward,
      {
        modelType: this.config.modelType,
        company: this.config.company,
        userIntent: this.previousAction,
        specificFeedback,
        feedbackType: this.getFeedbackType(finalReward),
        rewardBreakdown: this.lastRewardBreakdown,
        ...feedbackMetadata
      }
    );
    
    // Learn from experience if auto-learning is enabled
    if (this.config.autoLearn) {
      await this.learn([experience]);
    }
    
    // Reset for next action
    this.previousState = null;
    this.previousAction = null;
  }
  
  // Batch learning from multiple experiences
  async learn(experiences?: Experience[]) {
    const experiencesToLearn = experiences || this.collector.getRecentExperiences(32);
    
    if (experiencesToLearn.length === 0) {
      console.log('No experiences to learn from');
      return;
    }
    
    console.log(`Learning from ${experiencesToLearn.length} experiences`);
    
    // Update policy network
    await this.agent.updatePolicy(experiencesToLearn);
    
    // Save updated model
    await this.agent.saveModel();
    
    console.log('Policy updated and saved');
  }
  
  // Get suggested next action without executing
  async getSuggestion(
    currentGrid: Record<string, any>,
    userIntent: string
  ): Promise<PolicyAction> {
    await this.initialize();
    return this.agent.selectAction(
      currentGrid,
      userIntent,
      this.config.modelType
    );
  }
  
  // Get learning statistics
  async getStats() {
    const agentStats = this.agent.getStats();
    const avgReward = this.collector.getAverageReward();
    const recentExperiences = this.collector.getRecentExperiences(10);
    
    // Fetch from database
    let dbStats = null;
    try {
      const response = await fetch(`/api/agent/rl-experience?modelType=${this.config.modelType || 'General'}`);
      if (response.ok) {
        const data = await response.json();
        dbStats = data.stats;
      }
    } catch (error) {
      console.error('Failed to fetch DB stats:', error);
    }
    
    return {
      session: {
        id: this.currentSessionId,
        bufferSize: recentExperiences.length,
        avgReward,
        lastReward: recentExperiences[recentExperiences.length - 1]?.reward
      },
      agent: agentStats,
      database: dbStats,
      initialized: this.isInitialized
    };
  }
  
  // Export current session data
  exportSession() {
    return {
      sessionId: this.currentSessionId,
      config: this.config,
      experiences: this.collector.exportBuffer(),
      stats: this.agent.getStats()
    };
  }
  
  // Import session data (for replay/debugging)
  importSession(sessionData: any) {
    this.currentSessionId = sessionData.sessionId;
    this.config = sessionData.config;
    this.collector.importBuffer(sessionData.experiences);
    
    if (sessionData.config.epsilon !== undefined) {
      this.agent.setEpsilon(sessionData.config.epsilon);
    }
    if (sessionData.config.temperature !== undefined) {
      this.agent.setTemperature(sessionData.config.temperature);
    }
  }
  
  // Helper methods
  private generateSessionId(): string {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
  
  // Update exploration rate based on performance
  private updateExplorationRate(reward: number) {
    // Track performance
    this.performanceHistory.push(reward);
    if (this.performanceHistory.length > 100) {
      this.performanceHistory.shift(); // Keep last 100
    }
    
    // Calculate success rate
    const recentPerformance = this.performanceHistory.slice(-20);
    const successes = recentPerformance.filter(r => r > 0.5).length;
    this.successRate = successes / Math.max(1, recentPerformance.length);
    
    // Adaptive epsilon decay
    const currentEpsilon = this.agent.getEpsilon ? this.agent.getEpsilon() : 0.3;
    let newEpsilon = currentEpsilon;
    
    if (this.successRate > 0.7) {
      // Doing well, reduce exploration
      newEpsilon = Math.max(0.05, currentEpsilon * 0.95);
    } else if (this.successRate < 0.3) {
      // Doing poorly, increase exploration
      newEpsilon = Math.min(0.5, currentEpsilon * 1.1);
    } else {
      // Moderate performance, gradual decay
      newEpsilon = Math.max(0.1, currentEpsilon * 0.98);
    }
    
    this.agent.setEpsilon(newEpsilon);
    console.log(`Epsilon updated: ${currentEpsilon.toFixed(3)} → ${newEpsilon.toFixed(3)} (success rate: ${(this.successRate * 100).toFixed(1)}%)`);
  }
  
  // Decay epsilon manually (called from UI)
  decayEpsilon() {
    const current = this.agent.getEpsilon ? this.agent.getEpsilon() : 0.3;
    const newEpsilon = Math.max(0.05, current * 0.9);
    this.agent.setEpsilon(newEpsilon);
  }
  
  private getFeedbackType(reward: number): string {
    if (reward >= 0.8) return 'approve';
    if (reward >= 0.5) return 'good';
    if (reward >= 0) return 'neutral';
    if (reward >= -0.3) return 'edit';
    if (reward >= -0.6) return 'fix';
    return 'wrong';
  }
  
  // Decay exploration rate over time
  decayEpsilon(decayRate: number = 0.995) {
    const currentEpsilon = this.agent.getStats().epsilon;
    const newEpsilon = Math.max(0.01, currentEpsilon * decayRate);
    this.agent.setEpsilon(newEpsilon);
  }
  
  // Reset for new session
  reset() {
    this.currentSessionId = this.generateSessionId();
    this.previousState = null;
    this.previousAction = null;
    this.collector.clearBuffer();
  }

  // Get last reward breakdown for UI display
  getLastRewardBreakdown(): RewardBreakdown | null {
    return this.lastRewardBreakdown;
  }
}

// Export all components
export { LocalEmbeddings, ExperienceCollector, RAGPolicyAgent, RewardCalculator, SemanticFeedbackParser };
export type { Experience, PolicyAction, RewardBreakdown, SemanticFeedback };