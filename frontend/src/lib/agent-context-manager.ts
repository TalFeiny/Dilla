import { supabaseService } from '@/lib/supabase';

interface ConversationContext {
  sessionId: string;
  summary: string;
  keyTopics: string[];
  activeDeals: string[];
  analysisHistory: {
    companies: string[];
    markets: string[];
    metrics: Record<string, any>;
  };
  timestamp: Date;
}

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  tools?: string[];
  context?: any;
}

export class AgentContextManager {
  private maxMessagesInContext = 10;
  private summaryThreshold = 5;
  private contextWindow = 4096; // tokens
  
  constructor() {}

  /**
   * Manage conversation context to prevent rot
   */
  async manageContext(
    messages: Message[],
    sessionId: string
  ): Promise<{
    processedMessages: Message[];
    contextSummary: string;
    relevantContext: any;
  }> {
    // If messages exceed threshold, create summary
    if (messages.length > this.maxMessagesInContext) {
      const summary = await this.createContextSummary(
        messages.slice(0, -this.summaryThreshold),
        sessionId
      );
      
      // Keep only recent messages plus summary
      const recentMessages = messages.slice(-this.summaryThreshold);
      
      const processedMessages: Message[] = [
        {
          role: 'system',
          content: summary,
          timestamp: new Date()
        },
        ...recentMessages
      ];
      
      return {
        processedMessages,
        contextSummary: summary,
        relevantContext: await this.extractRelevantContext(recentMessages)
      };
    }
    
    return {
      processedMessages: messages,
      contextSummary: '',
      relevantContext: await this.extractRelevantContext(messages)
    };
  }

  /**
   * Create intelligent summary of conversation history
   */
  private async createContextSummary(
    messages: Message[],
    sessionId: string
  ): Promise<string> {
    // Extract key information from messages
    const companies = new Set<string>();
    const markets = new Set<string>();
    const metrics = new Map<string, any>();
    const decisions = [];
    const tools = new Set<string>();
    
    for (const msg of messages) {
      // Extract companies mentioned
      const companyMatches = msg.content.match(/\b[A-Z][a-zA-Z]+(?:Corp|Inc|Ltd|Co|AI|Tech|Labs)\b/g);
      if (companyMatches) {
        companyMatches.forEach(c => companies.add(c));
      }
      
      // Extract market sectors
      const marketKeywords = ['AI', 'Fintech', 'Healthcare', 'SaaS', 'Biotech', 'Crypto'];
      marketKeywords.forEach(market => {
        if (msg.content.toLowerCase().includes(market.toLowerCase())) {
          markets.add(market);
        }
      });
      
      // Extract metrics
      const irrMatch = msg.content.match(/(\d+)%\s*IRR/i);
      if (irrMatch) {
        metrics.set('targetIRR', irrMatch[1]);
      }
      
      const valuationMatch = msg.content.match(/\$(\d+(?:\.\d+)?[MBT])/g);
      if (valuationMatch) {
        metrics.set('valuations', valuationMatch);
      }
      
      // Track tools used
      if (msg.tools) {
        msg.tools.forEach(t => tools.add(t));
      }
      
      // Extract investment decisions
      const decisionKeywords = ['BUY', 'SELL', 'HOLD', 'PASS', 'INVEST'];
      decisionKeywords.forEach(decision => {
        if (msg.content.includes(decision)) {
          decisions.push(decision);
        }
      });
    }
    
    // Store context in database (non-critical — don't crash if Supabase is down)
    try {
      await this.storeContext(sessionId, {
        companies: Array.from(companies),
        markets: Array.from(markets),
        metrics: Object.fromEntries(metrics),
        decisions,
        tools: Array.from(tools)
      });
    } catch (storeErr) {
      console.warn('Failed to persist context to Supabase:', storeErr);
    }
    
    // Generate summary
    const summary = `## Previous Context Summary

### Analysis Focus
- **Companies Analyzed**: ${Array.from(companies).slice(0, 5).join(', ')}${companies.size > 5 ? ` (+${companies.size - 5} more)` : ''}
- **Markets Explored**: ${Array.from(markets).join(', ') || 'General'}
- **Tools Used**: ${Array.from(tools).join(', ') || 'None'}

### Key Metrics
- **Target IRR**: ${metrics.get('targetIRR') || '>50%'}
- **Valuations Discussed**: ${metrics.get('valuations')?.join(', ') || 'Various'}
- **Investment Decisions**: ${decisions.join(', ') || 'Evaluating'}

### Current Objective
Continuing alpha generation analysis with focus on ${markets.size > 0 ? `${Array.from(markets)[0]} sector` : 'high-IRR opportunities'}.`;
    
    return summary;
  }

  /**
   * Extract relevant context for current query
   */
  private async extractRelevantContext(messages: Message[]): Promise<any> {
    const context: any = {
      recentTopics: [],
      activeAnalysis: null,
      pendingActions: [],
      relevantData: {}
    };
    
    // Analyze recent messages for context
    const recentMessage = messages[messages.length - 1];
    if (recentMessage) {
      // Check for company names
      if (recentMessage.content.match(/[A-Z][a-zA-Z]+(?:Corp|Inc|Ltd|Co|AI|Tech|Labs)/)) {
        context.activeAnalysis = 'company_evaluation';
      }
      
      // Check for market analysis
      if (recentMessage.content.toLowerCase().includes('market') || 
          recentMessage.content.toLowerCase().includes('sector')) {
        context.activeAnalysis = 'market_analysis';
      }
      
      // Check for portfolio optimization
      if (recentMessage.content.toLowerCase().includes('portfolio') || 
          recentMessage.content.toLowerCase().includes('optimize')) {
        context.activeAnalysis = 'portfolio_optimization';
      }
    }
    
    return context;
  }

  /**
   * Store context in database for persistence
   */
  private async storeContext(
    sessionId: string,
    context: any
  ): Promise<void> {
    if (!supabaseService) {
      console.warn('Supabase service client not available, skipping context storage');
      return;
    }
    
    try {
      await supabaseService
        .from('agent_conversations')
        .insert({
          session_id: sessionId,
          user_message: 'Context Summary',
          agent_response: JSON.stringify(context),
          conversation_context: context,
          insights_generated: {
            companies: context.companies,
            markets: context.markets,
            metrics: context.metrics
          },
          alpha_opportunities_identified: context.companies?.length || 0
        });
    } catch (error) {
      console.error('Error storing context:', error);
    }
  }

  /**
   * Retrieve historical context for a session
   */
  async retrieveHistoricalContext(sessionId: string): Promise<ConversationContext | null> {
    if (!supabaseService) {
      console.warn('Supabase service client not available, cannot retrieve context');
      return null;
    }
    
    try {
      const { data, error } = await supabaseService
        .from('agent_conversations')
        .select('*')
        .eq('session_id', sessionId)
        .order('created_at', { ascending: false })
        .limit(1)
        .single();
      
      if (error || !data) return null;
      
      return {
        sessionId,
        summary: data.agent_response,
        keyTopics: data.insights_generated?.markets || [],
        activeDeals: data.insights_generated?.companies || [],
        analysisHistory: {
          companies: data.insights_generated?.companies || [],
          markets: data.insights_generated?.markets || [],
          metrics: data.insights_generated?.metrics || {}
        },
        timestamp: new Date(data.created_at)
      };
    } catch (error) {
      console.error('Error retrieving context:', error);
      return null;
    }
  }

  /**
   * Compress context using key information extraction
   */
  compressContext(text: string, maxTokens: number = 1000): string {
    // Extract key sentences based on importance markers
    const importanceMarkers = [
      'IRR', '%', '$', 'million', 'billion',
      'BUY', 'SELL', 'HOLD', 'alpha', 'opportunity',
      'undervalued', 'overvalued', 'recommendation'
    ];
    
    const sentences = text.split(/[.!?]+/);
    const scoredSentences = sentences.map(sentence => {
      let score = 0;
      importanceMarkers.forEach(marker => {
        if (sentence.toLowerCase().includes(marker.toLowerCase())) {
          score += 1;
        }
      });
      return { sentence: sentence.trim(), score };
    });
    
    // Sort by score and take top sentences
    scoredSentences.sort((a, b) => b.score - a.score);
    
    let compressed = '';
    let tokenCount = 0;
    
    for (const item of scoredSentences) {
      const sentenceTokens = item.sentence.split(' ').length;
      if (tokenCount + sentenceTokens <= maxTokens) {
        compressed += item.sentence + '. ';
        tokenCount += sentenceTokens;
      }
    }
    
    return compressed.trim();
  }

  /**
   * Calculate semantic similarity between messages
   */
  calculateSimilarity(msg1: string, msg2: string): number {
    // Simple Jaccard similarity for demonstration
    const words1 = new Set(msg1.toLowerCase().split(/\s+/));
    const words2 = new Set(msg2.toLowerCase().split(/\s+/));
    
    const intersection = new Set([...words1].filter(x => words2.has(x)));
    const union = new Set([...words1, ...words2]);
    
    return union.size === 0 ? 1.0 : intersection.size / union.size;
  }

  /**
   * Identify and remove redundant messages
   */
  deduplicateMessages(messages: Message[]): Message[] {
    const deduplicated: Message[] = [];
    
    for (let i = 0; i < messages.length; i++) {
      let isRedundant = false;
      
      for (let j = 0; j < deduplicated.length; j++) {
        const similarity = this.calculateSimilarity(
          messages[i].content,
          deduplicated[j].content
        );
        
        if (similarity > 0.8) {
          isRedundant = true;
          break;
        }
      }
      
      if (!isRedundant) {
        deduplicated.push(messages[i]);
      }
    }
    
    return deduplicated;
  }

  /**
   * Generate context-aware prompt additions
   */
  generateContextPrompt(context: any): string {
    let prompt = '';
    
    if (context.activeAnalysis === 'company_evaluation') {
      prompt += '\nFocus on company valuation and IRR calculations.';
    } else if (context.activeAnalysis === 'market_analysis') {
      prompt += '\nProvide market sizing and competitive landscape analysis.';
    } else if (context.activeAnalysis === 'portfolio_optimization') {
      prompt += '\nUse Kelly Criterion and correlation analysis for optimization.';
    }
    
    if (context.relevantData?.targetIRR) {
      prompt += `\nTarget IRR: ${context.relevantData.targetIRR}%`;
    }
    
    return prompt;
  }

  /**
   * Smart message pruning based on relevance
   */
  pruneMessages(
    messages: Message[],
    currentQuery: string,
    maxMessages: number = 5
  ): Message[] {
    // Score each message based on relevance to current query
    const scoredMessages: Array<{
      message: Message;
      relevance: number;
      recency: number;
      hasTools: number;
      combinedScore: number;
    }> = messages.map(msg => ({
      message: msg,
      relevance: this.calculateSimilarity(msg.content, currentQuery),
      recency: 1 / (messages.length - messages.indexOf(msg) + 1),
      hasTools: msg.tools && msg.tools.length > 0 ? 0.2 : 0,
      combinedScore: 0 // Will be calculated below
    }));
    
    // Calculate combined score
    scoredMessages.forEach(item => {
      item.combinedScore = 
        (item.relevance * 0.5) + 
        (item.recency * 0.3) + 
        (item.hasTools * 0.2);
    });
    
    // Sort by combined score and take top messages
    scoredMessages.sort((a, b) => b.combinedScore - a.combinedScore);
    
    return scoredMessages
      .slice(0, maxMessages)
      .map(item => item.message);
  }
}

// Export singleton instance
export const contextManager = new AgentContextManager();