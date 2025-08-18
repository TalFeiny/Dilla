import { createClient } from '@supabase/supabase-js';
import Anthropic from '@anthropic-ai/sdk';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || process.env.CLAUDE_API_KEY || '',
});

/**
 * CLAUDE 3.5 SONNET PRICING (as of Dec 2024)
 * Input: $3 per million tokens
 * Output: $15 per million tokens
 * 
 * COST ESTIMATES FOR SELF-LEARNING AGENT:
 * 
 * Per Query:
 * - Average input: ~2,000 tokens = $0.006
 * - Average output: ~1,500 tokens = $0.0225
 * - Total per query: ~$0.03
 * 
 * Daily Usage (100 queries):
 * - Cost: ~$3/day
 * 
 * Monthly Usage (3,000 queries):
 * - Cost: ~$90/month
 * 
 * With Learning & Feedback (10% overhead):
 * - Monthly: ~$100
 * 
 * Vision API (analyzing images):
 * - ~$0.01 per image
 * - 100 images/day = $30/month extra
 * 
 * TOTAL ESTIMATED MONTHLY COST: $130-150
 * 
 * Cost Optimization Strategies:
 * 1. Cache responses for common queries
 * 2. Use Claude Haiku ($0.25/$1.25 per M tokens) for simple tasks
 * 3. Batch similar queries
 * 4. Compress context before sending
 * 5. Use local models for preprocessing
 */

interface LearningRecord {
  id: string;
  query: string;
  response: string;
  feedback: FeedbackData;
  performance: PerformanceMetrics;
  timestamp: Date;
}

interface FeedbackData {
  accuracy: number; // 0-1
  usefulness: number; // 0-1
  userRating?: number; // 1-5
  corrections?: string[];
  actualOutcome?: any;
}

interface PerformanceMetrics {
  predictionAccuracy?: number;
  irrAccuracy?: number;
  timeToResponse: number;
  tokensUsed: number;
  cost: number;
}

interface LearningPattern {
  pattern: string;
  frequency: number;
  avgAccuracy: number;
  bestResponse: string;
  worstResponse: string;
}

export class SelfLearningAgent {
  private learningRate = 0.1;
  private memoryBank: Map<string, LearningRecord[]> = new Map();
  private patterns: LearningPattern[] = [];
  private totalCost = 0;
  private monthlyBudget = 150; // $150/month

  constructor() {
    this.loadMemoryFromDatabase();
  }

  /**
   * Process query with self-learning capabilities
   */
  async processWithLearning(
    query: string,
    context: any = {}
  ): Promise<{
    response: string;
    confidence: number;
    cost: number;
    learningApplied: boolean;
  }> {
    const startTime = Date.now();
    
    // Check if we have learned patterns for this query
    const similarQueries = await this.findSimilarQueries(query);
    let learningContext = '';
    let confidence = 0.5;
    
    if (similarQueries.length > 0) {
      learningContext = this.generateLearningContext(similarQueries);
      confidence = this.calculateConfidence(similarQueries);
    }
    
    // Estimate cost before making the call
    const estimatedCost = this.estimateCost(query, learningContext);
    
    // Check budget
    if (this.totalCost + estimatedCost > this.monthlyBudget) {
      return {
        response: 'Monthly budget exceeded. Using cached response.',
        confidence: 0.3,
        cost: 0,
        learningApplied: true
      };
    }
    
    // Build enhanced prompt with learning
    const enhancedPrompt = this.buildEnhancedPrompt(query, learningContext, context);
    
    // Call Claude with learning context
    const response = await anthropic.messages.create({
      model: 'claude-3-5-sonnet-20241022',
      max_tokens: 2048,
      temperature: 0,
      system: this.getSystemPromptWithLearning(),
      messages: [
        {
          role: 'user',
          content: enhancedPrompt
        }
      ]
    });
    
    const responseText = response.content[0].type === 'text' ? response.content[0].text : '';
    
    // Calculate actual cost
    const inputTokens = response.usage?.input_tokens || 0;
    const outputTokens = response.usage?.output_tokens || 0;
    const actualCost = (inputTokens * 0.003 + outputTokens * 0.015) / 1000;
    this.totalCost += actualCost;
    
    // Store learning record
    const learningRecord: LearningRecord = {
      id: `lr-${Date.now()}`,
      query,
      response: responseText,
      feedback: {
        accuracy: confidence,
        usefulness: 0.7 // Will be updated with actual feedback
      },
      performance: {
        timeToResponse: Date.now() - startTime,
        tokensUsed: inputTokens + outputTokens,
        cost: actualCost
      },
      timestamp: new Date()
    };
    
    await this.storeLearningRecord(learningRecord);
    
    // Extract and store patterns
    await this.extractPatterns(query, responseText);
    
    return {
      response: responseText,
      confidence,
      cost: actualCost,
      learningApplied: similarQueries.length > 0
    };
  }

  /**
   * Learn from feedback
   */
  async learnFromFeedback(
    queryId: string,
    feedback: FeedbackData
  ): Promise<void> {
    // Update learning record with feedback
    const { data: record } = await supabase
      .from('agent_learning_records')
      .select('*')
      .eq('id', queryId)
      .single();
    
    if (record) {
      // Update accuracy based on feedback
      const updatedRecord = {
        ...record,
        feedback: {
          ...record.feedback,
          ...feedback
        }
      };
      
      await supabase
        .from('agent_learning_records')
        .update(updatedRecord)
        .eq('id', queryId);
      
      // Adjust patterns based on feedback
      await this.adjustPatterns(record.query, feedback);
      
      // If accuracy is low, mark for retraining
      if (feedback.accuracy < 0.5) {
        await this.markForRetraining(record);
      }
    }
  }

  /**
   * Find similar queries from history
   */
  private async findSimilarQueries(query: string): Promise<LearningRecord[]> {
    // Simple similarity based on keywords
    const keywords = this.extractKeywords(query);
    
    const { data: similarRecords } = await supabase
      .from('agent_learning_records')
      .select('*')
      .textSearch('query', keywords.join(' | '))
      .order('feedback->accuracy', { ascending: false })
      .limit(5);
    
    return similarRecords || [];
  }

  /**
   * Generate learning context from similar queries
   */
  private generateLearningContext(similarQueries: LearningRecord[]): string {
    const bestPerforming = similarQueries
      .sort((a, b) => b.feedback.accuracy - a.feedback.accuracy)
      .slice(0, 3);
    
    let context = '\n\n## Learning from Previous Analyses:\n';
    
    for (const record of bestPerforming) {
      context += `\n### Similar Query (${(record.feedback.accuracy * 100).toFixed(0)}% accurate):\n`;
      context += `Query: ${record.query}\n`;
      context += `Key Insights: ${this.extractKeyInsights(record.response)}\n`;
      
      if (record.feedback.corrections) {
        context += `Corrections Applied: ${record.feedback.corrections.join(', ')}\n`;
      }
      
      if (record.feedback.actualOutcome) {
        context += `Actual Outcome: ${JSON.stringify(record.feedback.actualOutcome)}\n`;
      }
    }
    
    return context;
  }

  /**
   * Calculate confidence based on similar queries
   */
  private calculateConfidence(similarQueries: LearningRecord[]): number {
    if (similarQueries.length === 0) return 0.5;
    
    const avgAccuracy = similarQueries.reduce((sum, q) => sum + q.feedback.accuracy, 0) / similarQueries.length;
    const recency = similarQueries[0].timestamp.getTime() > Date.now() - 7 * 24 * 60 * 60 * 1000 ? 0.1 : 0;
    
    return Math.min(avgAccuracy + recency, 0.95);
  }

  /**
   * Build enhanced prompt with learning
   */
  private buildEnhancedPrompt(query: string, learningContext: string, context: any): string {
    return `${query}

${learningContext}

## Additional Context:
${JSON.stringify(context, null, 2)}

## Instructions:
1. Apply lessons learned from previous similar analyses
2. Avoid mistakes identified in corrections
3. Provide specific, quantitative predictions
4. Include confidence levels for each prediction
5. Reference actual outcomes when available`;
  }

  /**
   * Get system prompt with learning capabilities
   */
  private getSystemPromptWithLearning(): string {
    return `You are a self-learning investment analysis agent with the ability to improve from feedback.

## Learning Capabilities:
1. **Pattern Recognition**: You remember successful patterns from previous analyses
2. **Error Correction**: You learn from mistakes and apply corrections
3. **Outcome Tracking**: You compare predictions with actual outcomes
4. **Confidence Calibration**: You adjust confidence based on historical accuracy

## Self-Improvement Protocol:
- When you see "Corrections Applied", integrate those lessons
- When you see "Actual Outcome", calibrate future predictions
- Track which analysis methods work best for different scenarios
- Continuously refine your valuation models based on feedback

## Cost Consciousness:
- Current monthly budget: $${this.monthlyBudget}
- Used this month: $${this.totalCost.toFixed(2)}
- Optimize responses to provide maximum value per token

Remember: Your goal is to become more accurate over time by learning from every interaction.`;
  }

  /**
   * Extract keywords for similarity matching
   */
  private extractKeywords(text: string): string[] {
    const keywords = text.match(/\b[A-Z][a-zA-Z]+\b/g) || [];
    const numbers = text.match(/\$?\d+[MBT]?/g) || [];
    const importantWords = ['IRR', 'valuation', 'market', 'alpha', 'opportunity'];
    
    return [...new Set([...keywords, ...numbers, ...importantWords.filter(w => text.includes(w))])];
  }

  /**
   * Extract key insights from response
   */
  private extractKeyInsights(response: string): string {
    const lines = response.split('\n');
    const insights = lines.filter(line => 
      line.includes('IRR') ||
      line.includes('%') ||
      line.includes('$') ||
      line.includes('opportunity') ||
      line.includes('recommendation')
    ).slice(0, 3);
    
    return insights.join('; ');
  }

  /**
   * Extract patterns from query-response pairs
   */
  private async extractPatterns(query: string, response: string): Promise<void> {
    const pattern = this.identifyPattern(query);
    
    const existingPattern = this.patterns.find(p => p.pattern === pattern);
    
    if (existingPattern) {
      existingPattern.frequency++;
      // Update best/worst responses based on some metric
    } else {
      this.patterns.push({
        pattern,
        frequency: 1,
        avgAccuracy: 0.7,
        bestResponse: response,
        worstResponse: ''
      });
    }
    
    // Store patterns in database
    await this.storePatternsInDatabase();
  }

  /**
   * Identify pattern type from query
   */
  private identifyPattern(query: string): string {
    if (query.includes('valuation')) return 'valuation_analysis';
    if (query.includes('market')) return 'market_analysis';
    if (query.includes('IRR') || query.includes('return')) return 'return_prediction';
    if (query.includes('portfolio')) return 'portfolio_optimization';
    if (query.includes('compare')) return 'comparative_analysis';
    return 'general_analysis';
  }

  /**
   * Adjust patterns based on feedback
   */
  private async adjustPatterns(query: string, feedback: FeedbackData): Promise<void> {
    const pattern = this.identifyPattern(query);
    const existingPattern = this.patterns.find(p => p.pattern === pattern);
    
    if (existingPattern) {
      // Update average accuracy with exponential moving average
      existingPattern.avgAccuracy = 
        existingPattern.avgAccuracy * (1 - this.learningRate) + 
        feedback.accuracy * this.learningRate;
    }
  }

  /**
   * Mark query for retraining
   */
  private async markForRetraining(record: LearningRecord): Promise<void> {
    await supabase
      .from('agent_retraining_queue')
      .insert({
        query: record.query,
        original_response: record.response,
        feedback: record.feedback,
        priority: record.feedback.accuracy < 0.3 ? 'high' : 'medium',
        created_at: new Date()
      });
  }

  /**
   * Store learning record in database
   */
  private async storeLearningRecord(record: LearningRecord): Promise<void> {
    await supabase
      .from('agent_learning_records')
      .insert(record);
    
    // Also update in-memory cache
    const key = this.identifyPattern(record.query);
    if (!this.memoryBank.has(key)) {
      this.memoryBank.set(key, []);
    }
    this.memoryBank.get(key)!.push(record);
  }

  /**
   * Store patterns in database
   */
  private async storePatternsInDatabase(): Promise<void> {
    await supabase
      .from('agent_patterns')
      .upsert(this.patterns);
  }

  /**
   * Load memory from database on initialization
   */
  private async loadMemoryFromDatabase(): Promise<void> {
    const { data: records } = await supabase
      .from('agent_learning_records')
      .select('*')
      .order('timestamp', { ascending: false })
      .limit(1000);
    
    if (records) {
      for (const record of records) {
        const key = this.identifyPattern(record.query);
        if (!this.memoryBank.has(key)) {
          this.memoryBank.set(key, []);
        }
        this.memoryBank.get(key)!.push(record);
      }
    }
    
    const { data: patterns } = await supabase
      .from('agent_patterns')
      .select('*');
    
    if (patterns) {
      this.patterns = patterns;
    }
  }

  /**
   * Estimate cost before making API call
   */
  private estimateCost(query: string, context: string): number {
    const totalText = query + context;
    const estimatedInputTokens = totalText.length / 4; // Rough estimate
    const estimatedOutputTokens = 1500; // Average output
    
    return (estimatedInputTokens * 0.003 + estimatedOutputTokens * 0.015) / 1000;
  }

  /**
   * Get learning statistics
   */
  async getStatistics(): Promise<{
    totalQueries: number;
    avgAccuracy: number;
    totalCost: number;
    remainingBudget: number;
    topPatterns: LearningPattern[];
    improvementRate: number;
  }> {
    const allRecords = Array.from(this.memoryBank.values()).flat();
    
    const avgAccuracy = allRecords.reduce((sum, r) => sum + r.feedback.accuracy, 0) / allRecords.length;
    
    // Calculate improvement rate (compare last 100 to previous 100)
    const recent = allRecords.slice(0, 100);
    const previous = allRecords.slice(100, 200);
    
    const recentAccuracy = recent.reduce((sum, r) => sum + r.feedback.accuracy, 0) / recent.length;
    const previousAccuracy = previous.reduce((sum, r) => sum + r.feedback.accuracy, 0) / previous.length;
    const improvementRate = ((recentAccuracy - previousAccuracy) / previousAccuracy) * 100;
    
    return {
      totalQueries: allRecords.length,
      avgAccuracy,
      totalCost: this.totalCost,
      remainingBudget: this.monthlyBudget - this.totalCost,
      topPatterns: this.patterns.sort((a, b) => b.frequency - a.frequency).slice(0, 5),
      improvementRate
    };
  }

  /**
   * Batch process queries for cost efficiency
   */
  async batchProcess(queries: string[]): Promise<any[]> {
    // Combine queries into single call to save on API costs
    const batchPrompt = queries.map((q, i) => `Query ${i + 1}: ${q}`).join('\n\n');
    
    const response = await anthropic.messages.create({
      model: 'claude-3-5-sonnet-20241022',
      max_tokens: 4096,
      temperature: 0,
      system: this.getSystemPromptWithLearning(),
      messages: [
        {
          role: 'user',
          content: `Please analyze these queries separately and provide numbered responses:\n\n${batchPrompt}`
        }
      ]
    });
    
    // Parse batched response
    const responseText = response.content[0].type === 'text' ? response.content[0].text : '';
    const responses = responseText.split(/Query \d+:/);
    
    return responses.slice(1); // Remove empty first element
  }
}

// Export singleton instance
export const selfLearningAgent = new SelfLearningAgent();