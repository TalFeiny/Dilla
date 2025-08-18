/**
 * Reinforcement Learning with Human Feedback (RLHF) System
 * Trains the agent to build better financial models through reward signals
 */

import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

interface Action {
  command: string;
  cell: string;
  value: any;
  formula?: string;
}

interface State {
  company: string;
  modelType: string;
  availableData: Record<string, any>;
  currentGrid: Record<string, any>;
  step: number;
}

interface Trajectory {
  states: State[];
  actions: Action[];
  rewards: number[];
  finalReward: number;
}

export class RLFeedbackSystem {
  private currentTrajectory: Partial<Trajectory> | null = null;
  private currentState: State | null = null;

  // Initialize a new RL session
  async startEpisode(company: string, modelType: string, availableData: Record<string, any>) {
    this.currentState = {
      company,
      modelType,
      availableData,
      currentGrid: {},
      step: 0
    };

    this.currentTrajectory = {
      states: [this.currentState],
      actions: [],
      rewards: [],
      finalReward: 0
    };

    return crypto.randomUUID();
  }

  // Record an action taken by the agent
  async recordAction(action: Action) {
    if (!this.currentTrajectory || !this.currentState) return;

    this.currentTrajectory.actions?.push(action);
    
    // Update state based on action
    if (action.cell) {
      this.currentState.currentGrid[action.cell] = action.value;
    }
    this.currentState.step++;
    
    // Clone state for trajectory
    this.currentTrajectory.states?.push({ ...this.currentState });
  }

  // Record immediate reward/penalty from user feedback
  async recordReward(reward: number, reason?: string) {
    if (!this.currentTrajectory) return;

    this.currentTrajectory.rewards?.push(reward);

    // Store feedback event
    await supabase.from('rl_feedback').insert({
      trajectory_id: crypto.randomUUID(),
      step: this.currentState?.step || 0,
      reward,
      reason,
      state: this.currentState,
      created_at: new Date()
    });
  }

  // Calculate reward based on user actions
  calculateReward(userAction: string): number {
    const rewards: Record<string, number> = {
      // Positive rewards
      'approve': 1.0,
      'good': 0.8,
      'correct': 0.7,
      'keep': 0.5,
      
      // Negative rewards
      'delete': -1.0,
      'wrong': -0.8,
      'fix': -0.6,
      'change': -0.4,
      'why': -0.2,  // User confusion is negative signal
      
      // Neutral
      'edit': -0.1,  // Minor adjustment needed
    };

    // Check which reward applies
    for (const [action, reward] of Object.entries(rewards)) {
      if (userAction.toLowerCase().includes(action)) {
        return reward;
      }
    }

    return 0; // Neutral if no clear signal
  }

  // Learn from a complete trajectory using TD learning
  async learnFromTrajectory(finalScore: number) {
    if (!this.currentTrajectory) return;

    this.currentTrajectory.finalReward = finalScore;

    // Calculate discounted returns (TD learning)
    const gamma = 0.95; // Discount factor
    const returns: number[] = [];
    let G = finalScore;

    // Work backwards through trajectory
    for (let t = (this.currentTrajectory.rewards?.length || 0) - 1; t >= 0; t--) {
      G = (this.currentTrajectory.rewards?.[t] || 0) + gamma * G;
      returns.unshift(G);
    }

    // Store trajectory with computed returns
    const { error } = await supabase.from('rl_trajectories').insert({
      company: this.currentState?.company,
      model_type: this.currentState?.modelType,
      trajectory: this.currentTrajectory,
      returns,
      final_score: finalScore,
      created_at: new Date()
    });

    if (!error) {
      // Update value function approximation
      await this.updateValueFunction(returns);
      
      // Update policy if score is good
      if (finalScore > 0.7) {
        await this.updatePolicy();
      }
    }

    // Reset for next episode
    this.currentTrajectory = null;
    this.currentState = null;
  }

  // Update value function using TD error
  async updateValueFunction(returns: number[]) {
    if (!this.currentTrajectory) return;

    const alpha = 0.1; // Learning rate

    for (let t = 0; t < returns.length - 1; t++) {
      const state = this.currentTrajectory.states?.[t];
      const nextState = this.currentTrajectory.states?.[t + 1];
      const reward = this.currentTrajectory.rewards?.[t] || 0;
      
      if (!state || !nextState) continue;

      // TD error: δ = r + γV(s') - V(s)
      const tdError = reward + 0.95 * returns[t + 1] - returns[t];

      // Store TD error for this state-action pair
      await supabase.from('rl_td_errors').insert({
        state_hash: this.hashState(state),
        action: JSON.stringify(this.currentTrajectory.actions?.[t]),
        td_error: tdError,
        return_value: returns[t],
        created_at: new Date()
      });
    }
  }

  // Update policy based on successful trajectories
  async updatePolicy() {
    if (!this.currentTrajectory) return;

    // Extract successful action sequences
    const successfulPattern = {
      model_type: this.currentState?.modelType,
      company_sector: this.currentState?.company,
      action_sequence: this.currentTrajectory.actions,
      data_used: Object.keys(this.currentState?.availableData || {}),
      score: this.currentTrajectory.finalReward
    };

    // Store as positive example
    await supabase.from('rl_policy_examples').insert({
      pattern: successfulPattern,
      weight: this.currentTrajectory.finalReward, // Higher weight for better models
      created_at: new Date()
    });
  }

  // Get best action based on current policy
  async getBestAction(state: State): Promise<Action | null> {
    // Query similar states and their best actions
    const stateHash = this.hashState(state);
    
    const { data } = await supabase
      .from('rl_td_errors')
      .select('action, return_value')
      .eq('state_hash', stateHash)
      .order('return_value', { ascending: false })
      .limit(1);

    if (data && data.length > 0) {
      return JSON.parse(data[0].action);
    }

    // Fallback: get from successful patterns
    const { data: patterns } = await supabase
      .from('rl_policy_examples')
      .select('pattern')
      .eq('pattern->>model_type', state.modelType)
      .order('weight', { ascending: false })
      .limit(1);

    if (patterns && patterns.length > 0) {
      const sequence = patterns[0].pattern.action_sequence;
      return sequence[Math.min(state.step, sequence.length - 1)];
    }

    return null;
  }

  // Generate reward-weighted training examples
  async generateRLTrainingData(): Promise<any[]> {
    const { data } = await supabase
      .from('rl_trajectories')
      .select('*')
      .gte('final_score', 0.7)
      .order('final_score', { ascending: false })
      .limit(100);

    if (!data) return [];

    // Convert to training format with reward weighting
    return data.map(traj => {
      const weight = traj.final_score;
      const actions = traj.trajectory.actions;
      
      return {
        messages: [
          {
            role: 'system',
            content: `You are a financial modeling expert. Your reward score was ${weight}.`
          },
          {
            role: 'user',
            content: `Build a ${traj.model_type} model for ${traj.company}`
          },
          {
            role: 'assistant',
            content: actions.map((a: Action) => 
              `grid.write("${a.cell}", ${JSON.stringify(a.value)})`
            ).join('\n')
          }
        ],
        weight // Use for importance sampling in training
      };
    });
  }

  // Get cumulative learning stats
  async getLearningStats(): Promise<any> {
    const { data: trajectories } = await supabase
      .from('rl_trajectories')
      .select('final_score, model_type, created_at')
      .order('created_at', { ascending: true });

    if (!trajectories) return {};

    // Calculate moving average of scores
    const window = 10;
    const movingAverages: Record<string, number[]> = {};

    trajectories.forEach((traj, i) => {
      const modelType = traj.model_type;
      if (!movingAverages[modelType]) {
        movingAverages[modelType] = [];
      }

      const start = Math.max(0, i - window + 1);
      const relevantScores = trajectories
        .slice(start, i + 1)
        .filter(t => t.model_type === modelType)
        .map(t => t.final_score);

      const avg = relevantScores.reduce((a, b) => a + b, 0) / relevantScores.length;
      movingAverages[modelType].push(avg);
    });

    return {
      totalEpisodes: trajectories.length,
      averageScore: trajectories.reduce((a, b) => a + b.final_score, 0) / trajectories.length,
      learningCurves: movingAverages,
      improvement: this.calculateImprovement(movingAverages)
    };
  }

  private calculateImprovement(curves: Record<string, number[]>): Record<string, number> {
    const improvements: Record<string, number> = {};
    
    Object.entries(curves).forEach(([modelType, scores]) => {
      if (scores.length < 2) {
        improvements[modelType] = 0;
      } else {
        const early = scores.slice(0, 5).reduce((a, b) => a + b, 0) / Math.min(5, scores.length);
        const recent = scores.slice(-5).reduce((a, b) => a + b, 0) / Math.min(5, scores.length);
        improvements[modelType] = ((recent - early) / early) * 100;
      }
    });
    
    return improvements;
  }

  private hashState(state: State): string {
    // Create deterministic hash of state
    const key = `${state.modelType}_${state.company}_${state.step}_${Object.keys(state.availableData).sort().join('_')}`;
    return Buffer.from(key).toString('base64').substring(0, 32);
  }
}

export const rlSystem = new RLFeedbackSystem();