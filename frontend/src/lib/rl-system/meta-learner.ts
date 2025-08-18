/**
 * Meta-Learning System
 * Learns when to apply specific frameworks vs. generalization
 */

import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

interface ApproachResult {
  approach: 'template' | 'learned' | 'hybrid' | 'exploration';
  success: boolean;
  reward: number;
  context: any;
}

export class MetaLearner {
  private approachHistory: Map<string, ApproachResult[]> = new Map();
  
  /**
   * Decide which approach to use based on query characteristics
   */
  async selectApproach(query: string, context: any): Promise<string> {
    // Get query embedding for similarity search
    const queryFeatures = this.extractQueryFeatures(query);
    
    // Find similar past queries
    const similarExperiences = await this.findSimilarExperiences(queryFeatures);
    
    if (similarExperiences.length === 0) {
      // No similar experiences - use exploration
      return 'exploration';
    }
    
    // Analyze which approach worked best for similar queries
    const approachScores = this.calculateApproachScores(similarExperiences);
    
    // Add exploration bonus to avoid local optima
    const explorationBonus = Math.random() < this.getExplorationRate() ? 0.3 : 0;
    
    // Select best approach with some randomness
    return this.selectBestApproach(approachScores, explorationBonus);
  }
  
  /**
   * Learn from approach outcome
   */
  async recordOutcome(
    query: string,
    approach: string,
    success: boolean,
    reward: number
  ): Promise<void> {
    const result: ApproachResult = {
      approach: approach as any,
      success,
      reward,
      context: this.extractQueryFeatures(query)
    };
    
    // Store locally
    const key = this.getQueryCategory(query);
    if (!this.approachHistory.has(key)) {
      this.approachHistory.set(key, []);
    }
    this.approachHistory.get(key)!.push(result);
    
    // Store in database for persistence
    await supabase.from('meta_learning_history').insert({
      query_features: result.context,
      approach,
      success,
      reward,
      created_at: new Date()
    });
    
    // Update approach preferences
    await this.updateApproachPreferences(key, approach, reward);
  }
  
  /**
   * Get recommended framework level for query type
   */
  getFrameworkLevel(query: string): 'strict' | 'flexible' | 'none' {
    const features = this.extractQueryFeatures(query);
    
    // High structure needed for specific financial models
    if (features.specificity > 0.8 && features.hasStandardModel) {
      return 'strict';
    }
    
    // Flexible framework for semi-structured tasks
    if (features.specificity > 0.5) {
      return 'flexible';
    }
    
    // No framework for exploratory tasks
    return 'none';
  }
  
  /**
   * Extract features for meta-learning
   */
  private extractQueryFeatures(query: string): any {
    return {
      length: query.length,
      wordCount: query.split(/\s+/).length,
      specificity: this.calculateSpecificity(query),
      hasStandardModel: /dcf|npv|irr|payback|projection/i.test(query),
      hasCustomRequirement: /custom|specific|unique|special/i.test(query),
      complexity: this.calculateComplexity(query),
      domain: this.identifyDomain(query)
    };
  }
  
  /**
   * Calculate how specific vs. general a query is
   */
  private calculateSpecificity(query: string): number {
    let score = 0;
    
    // Specific numbers increase specificity
    const numbers = query.match(/\d+\.?\d*/g) || [];
    score += Math.min(numbers.length * 0.1, 0.3);
    
    // Named entities increase specificity
    const properNouns = query.match(/[A-Z][a-z]+/g) || [];
    score += Math.min(properNouns.length * 0.1, 0.3);
    
    // Standard terms increase specificity
    const standardTerms = ['dcf', 'revenue', 'ebitda', 'margin', 'growth rate'];
    const termCount = standardTerms.filter(term => 
      new RegExp(term, 'i').test(query)
    ).length;
    score += termCount * 0.1;
    
    // Vague terms decrease specificity
    const vagueTerms = ['help', 'something', 'stuff', 'thing', 'maybe'];
    const vagueCount = vagueTerms.filter(term => 
      new RegExp(term, 'i').test(query)
    ).length;
    score -= vagueCount * 0.1;
    
    return Math.min(Math.max(score, 0), 1);
  }
  
  /**
   * Calculate query complexity
   */
  private calculateComplexity(query: string): number {
    let complexity = 0;
    
    // Multiple steps increase complexity
    const steps = query.split(/then|and then|after that|next/i).length - 1;
    complexity += steps * 0.2;
    
    // Multiple metrics increase complexity
    const metrics = query.match(/revenue|cost|profit|margin|growth|ebitda/gi) || [];
    complexity += Math.min(metrics.length * 0.1, 0.3);
    
    // Conditional logic increases complexity
    if (/if|when|unless|otherwise/i.test(query)) {
      complexity += 0.2;
    }
    
    return Math.min(complexity, 1);
  }
  
  /**
   * Identify domain of query
   */
  private identifyDomain(query: string): string {
    const domains = {
      financial: /revenue|profit|margin|cash|financial|money|budget/i,
      valuation: /valuation|value|worth|exit|multiple|pwerm/i,
      operational: /operations|efficiency|productivity|utilization/i,
      strategic: /strategy|market|competition|growth|expansion/i
    };
    
    for (const [domain, pattern] of Object.entries(domains)) {
      if (pattern.test(query)) return domain;
    }
    
    return 'general';
  }
  
  /**
   * Find similar past experiences
   */
  private async findSimilarExperiences(features: any): Promise<any[]> {
    // Use vector similarity or feature matching
    const { data } = await supabase
      .from('meta_learning_history')
      .select('*')
      .gte('created_at', new Date(Date.now() - 7 * 24 * 60 * 60 * 1000)) // Last 7 days
      .order('reward', { ascending: false })
      .limit(10);
    
    if (!data) return [];
    
    // Filter by similarity
    return data.filter(exp => {
      const expFeatures = exp.query_features;
      const similarity = this.calculateSimilarity(features, expFeatures);
      return similarity > 0.7;
    });
  }
  
  /**
   * Calculate feature similarity
   */
  private calculateSimilarity(f1: any, f2: any): number {
    if (!f1 || !f2) return 0;
    
    let similarity = 0;
    let count = 0;
    
    // Numeric features
    if (f1.specificity !== undefined && f2.specificity !== undefined) {
      similarity += 1 - Math.abs(f1.specificity - f2.specificity);
      count++;
    }
    
    if (f1.complexity !== undefined && f2.complexity !== undefined) {
      similarity += 1 - Math.abs(f1.complexity - f2.complexity);
      count++;
    }
    
    // Boolean features
    if (f1.hasStandardModel === f2.hasStandardModel) {
      similarity += 1;
      count++;
    }
    
    // Categorical features
    if (f1.domain === f2.domain) {
      similarity += 1;
      count++;
    }
    
    return count > 0 ? similarity / count : 0;
  }
  
  /**
   * Calculate scores for each approach
   */
  private calculateApproachScores(experiences: any[]): Record<string, number> {
    const scores: Record<string, number> = {
      template: 0,
      learned: 0,
      hybrid: 0,
      exploration: 0.1 // Base exploration score
    };
    
    for (const exp of experiences) {
      if (exp.approach && exp.reward !== undefined) {
        scores[exp.approach] = (scores[exp.approach] || 0) + exp.reward;
      }
    }
    
    // Normalize
    const total = Object.values(scores).reduce((a, b) => a + b, 0);
    if (total > 0) {
      for (const key in scores) {
        scores[key] /= total;
      }
    }
    
    return scores;
  }
  
  /**
   * Select best approach with exploration
   */
  private selectBestApproach(
    scores: Record<string, number>,
    explorationBonus: number
  ): string {
    // Add exploration bonus to least-tried approaches
    const modifiedScores = { ...scores };
    modifiedScores.exploration += explorationBonus;
    
    // Select probabilistically
    const total = Object.values(modifiedScores).reduce((a, b) => a + b, 0);
    let random = Math.random() * total;
    
    for (const [approach, score] of Object.entries(modifiedScores)) {
      random -= score;
      if (random <= 0) return approach;
    }
    
    return 'hybrid'; // Default
  }
  
  /**
   * Get exploration rate (decreases over time)
   */
  private getExplorationRate(): number {
    const totalExperiences = Array.from(this.approachHistory.values())
      .reduce((sum, arr) => sum + arr.length, 0);
    
    // Start at 30%, decrease to 5%
    return Math.max(0.05, 0.3 * Math.exp(-totalExperiences / 100));
  }
  
  /**
   * Get query category for grouping
   */
  private getQueryCategory(query: string): string {
    const features = this.extractQueryFeatures(query);
    return `${features.domain}_${Math.round(features.specificity * 10)}_${Math.round(features.complexity * 10)}`;
  }
  
  /**
   * Update approach preferences
   */
  private async updateApproachPreferences(
    category: string,
    approach: string,
    reward: number
  ): Promise<void> {
    // Update running average of approach performance
    const { data: existing } = await supabase
      .from('approach_preferences')
      .select('*')
      .eq('category', category)
      .eq('approach', approach)
      .single();
    
    if (existing) {
      const newAvg = (existing.avg_reward * existing.count + reward) / (existing.count + 1);
      await supabase
        .from('approach_preferences')
        .update({
          avg_reward: newAvg,
          count: existing.count + 1,
          updated_at: new Date()
        })
        .eq('id', existing.id);
    } else {
      await supabase
        .from('approach_preferences')
        .insert({
          category,
          approach,
          avg_reward: reward,
          count: 1,
          created_at: new Date()
        });
    }
  }
}

export const metaLearner = new MetaLearner();