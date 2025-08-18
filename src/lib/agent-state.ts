/**
 * Agent State Management System
 * Persistent conversation and context storage with Redis/Supabase fallback
 */

import { createClient } from '@supabase/supabase-js';
import { Redis } from '@upstash/redis';

// State interfaces
export interface AgentMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  mode?: string;
  tools?: string[];
  metadata?: Record<string, any>;
  timestamp: Date;
}

export interface AgentContext {
  // Current focus
  currentCompany?: string;
  currentFund?: string;
  currentAnalysis?: string;
  currentDocument?: string;
  
  // User preferences
  preferredMode?: string;
  verbosity?: 'concise' | 'detailed' | 'verbose';
  autoTools?: boolean;
  
  // Recent activity
  recentSearches: string[];
  recentCompanies: string[];
  recentAnalyses: string[];
  
  // Cached data
  cachedMetrics?: Record<string, any>;
  cachedMarketData?: Record<string, any>;
  
  // Session info
  sessionId: string;
  userId?: string;
  startedAt: Date;
  lastActive: Date;
}

export interface ConversationState {
  id: string;
  messages: AgentMessage[];
  context: AgentContext;
  summary?: string;
  tags?: string[];
  createdAt: Date;
  updatedAt: Date;
}

// Storage backends
export enum StorageBackend {
  MEMORY = 'memory',
  REDIS = 'redis',
  SUPABASE = 'supabase'
}

/**
 * Agent State Manager
 * Handles persistent storage of conversations and context
 */
export class AgentStateManager {
  private backend: StorageBackend;
  private memoryStore: Map<string, ConversationState>;
  private redis?: Redis;
  private supabase?: any;
  
  constructor(backend: StorageBackend = StorageBackend.MEMORY) {
    this.backend = backend;
    this.memoryStore = new Map();
    
    // Initialize storage backends
    this.initializeBackends();
  }
  
  private initializeBackends() {
    // Redis setup (if available)
    if (this.backend === StorageBackend.REDIS) {
      const redisUrl = process.env.UPSTASH_REDIS_REST_URL;
      const redisToken = process.env.UPSTASH_REDIS_REST_TOKEN;
      
      if (redisUrl && redisToken) {
        this.redis = new Redis({
          url: redisUrl,
          token: redisToken
        });
      } else {
        console.warn('Redis credentials not found, falling back to memory');
        this.backend = StorageBackend.MEMORY;
      }
    }
    
    // Supabase setup (if available)
    if (this.backend === StorageBackend.SUPABASE) {
      const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
      const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
      
      if (supabaseUrl && supabaseKey) {
        this.supabase = createClient(supabaseUrl, supabaseKey);
      } else {
        console.warn('Supabase credentials not found, falling back to memory');
        this.backend = StorageBackend.MEMORY;
      }
    }
  }
  
  /**
   * Create a new conversation
   */
  async createConversation(userId?: string): Promise<ConversationState> {
    const conversation: ConversationState = {
      id: this.generateId(),
      messages: [],
      context: {
        recentSearches: [],
        recentCompanies: [],
        recentAnalyses: [],
        sessionId: this.generateId(),
        userId,
        startedAt: new Date(),
        lastActive: new Date()
      },
      createdAt: new Date(),
      updatedAt: new Date()
    };
    
    await this.saveConversation(conversation);
    return conversation;
  }
  
  /**
   * Get conversation by ID
   */
  async getConversation(id: string): Promise<ConversationState | null> {
    switch (this.backend) {
      case StorageBackend.MEMORY:
        return this.memoryStore.get(id) || null;
        
      case StorageBackend.REDIS:
        if (this.redis) {
          const data = await this.redis.get(`conversation:${id}`);
          return data ? this.deserializeConversation(data) : null;
        }
        return null;
        
      case StorageBackend.SUPABASE:
        if (this.supabase) {
          const { data, error } = await this.supabase
            .from('agent_conversations')
            .select('*')
            .eq('id', id)
            .single();
          
          return error ? null : this.deserializeConversation(data);
        }
        return null;
        
      default:
        return null;
    }
  }
  
  /**
   * Save conversation state
   */
  async saveConversation(conversation: ConversationState): Promise<void> {
    conversation.updatedAt = new Date();
    
    switch (this.backend) {
      case StorageBackend.MEMORY:
        this.memoryStore.set(conversation.id, conversation);
        this.cleanupOldConversations();
        break;
        
      case StorageBackend.REDIS:
        if (this.redis) {
          await this.redis.setex(
            `conversation:${conversation.id}`,
            86400, // 24 hours TTL
            JSON.stringify(conversation)
          );
        }
        break;
        
      case StorageBackend.SUPABASE:
        if (this.supabase) {
          await this.supabase
            .from('agent_conversations')
            .upsert({
              id: conversation.id,
              messages: conversation.messages,
              context: conversation.context,
              summary: conversation.summary,
              tags: conversation.tags,
              created_at: conversation.createdAt,
              updated_at: conversation.updatedAt
            });
        }
        break;
    }
  }
  
  /**
   * Add message to conversation
   */
  async addMessage(
    conversationId: string,
    message: Omit<AgentMessage, 'id' | 'timestamp'>
  ): Promise<AgentMessage> {
    const conversation = await this.getConversation(conversationId);
    if (!conversation) {
      throw new Error('Conversation not found');
    }
    
    const fullMessage: AgentMessage = {
      ...message,
      id: this.generateId(),
      timestamp: new Date()
    };
    
    conversation.messages.push(fullMessage);
    conversation.context.lastActive = new Date();
    
    // Update context based on message
    this.updateContextFromMessage(conversation.context, fullMessage);
    
    // Generate summary if conversation is long
    if (conversation.messages.length % 10 === 0) {
      conversation.summary = await this.generateConversationSummary(conversation);
    }
    
    await this.saveConversation(conversation);
    return fullMessage;
  }
  
  /**
   * Update context from message content
   */
  private updateContextFromMessage(context: AgentContext, message: AgentMessage) {
    // Extract company names
    const companyPattern = /\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b/g;
    const companies = message.content.match(companyPattern) || [];
    companies.forEach(company => {
      if (!context.recentCompanies.includes(company)) {
        context.recentCompanies.unshift(company);
        context.recentCompanies = context.recentCompanies.slice(0, 10);
      }
    });
    
    // Track searches
    if (message.content.toLowerCase().includes('search') || 
        message.content.toLowerCase().includes('research')) {
      context.recentSearches.unshift(message.content.substring(0, 100));
      context.recentSearches = context.recentSearches.slice(0, 10);
    }
    
    // Track analyses
    if (message.content.toLowerCase().includes('analysis') ||
        message.content.toLowerCase().includes('pwerm')) {
      context.recentAnalyses.unshift(message.content.substring(0, 100));
      context.recentAnalyses = context.recentAnalyses.slice(0, 5);
    }
  }
  
  /**
   * Get conversation context
   */
  async getContext(conversationId: string): Promise<AgentContext | null> {
    const conversation = await this.getConversation(conversationId);
    return conversation?.context || null;
  }
  
  /**
   * Update conversation context
   */
  async updateContext(
    conversationId: string,
    updates: Partial<AgentContext>
  ): Promise<void> {
    const conversation = await this.getConversation(conversationId);
    if (!conversation) {
      throw new Error('Conversation not found');
    }
    
    conversation.context = {
      ...conversation.context,
      ...updates,
      lastActive: new Date()
    };
    
    await this.saveConversation(conversation);
  }
  
  /**
   * Search conversations
   */
  async searchConversations(query: string, userId?: string): Promise<ConversationState[]> {
    switch (this.backend) {
      case StorageBackend.MEMORY:
        return Array.from(this.memoryStore.values()).filter(conv => {
          const matchesUser = !userId || conv.context.userId === userId;
          const matchesQuery = conv.messages.some(m => 
            m.content.toLowerCase().includes(query.toLowerCase())
          );
          return matchesUser && matchesQuery;
        });
        
      case StorageBackend.SUPABASE:
        if (this.supabase) {
          let queryBuilder = this.supabase
            .from('agent_conversations')
            .select('*');
          
          if (userId) {
            queryBuilder = queryBuilder.eq('context->userId', userId);
          }
          
          const { data, error } = await queryBuilder
            .textSearch('messages', query)
            .limit(20);
          
          return error ? [] : data.map((d: any) => this.deserializeConversation(d));
        }
        return [];
        
      default:
        return [];
    }
  }
  
  /**
   * Get user's recent conversations
   */
  async getUserConversations(userId: string, limit: number = 10): Promise<ConversationState[]> {
    switch (this.backend) {
      case StorageBackend.MEMORY:
        return Array.from(this.memoryStore.values())
          .filter(conv => conv.context.userId === userId)
          .sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime())
          .slice(0, limit);
        
      case StorageBackend.SUPABASE:
        if (this.supabase) {
          const { data, error } = await this.supabase
            .from('agent_conversations')
            .select('*')
            .eq('context->userId', userId)
            .order('updated_at', { ascending: false })
            .limit(limit);
          
          return error ? [] : data.map((d: any) => this.deserializeConversation(d));
        }
        return [];
        
      default:
        return [];
    }
  }
  
  /**
   * Generate conversation summary using AI
   */
  private async generateConversationSummary(conversation: ConversationState): Promise<string> {
    // This would call Claude or GPT to summarize
    const messageCount = conversation.messages.length;
    const topics = [...new Set(conversation.context.recentCompanies)].join(', ');
    return `Conversation with ${messageCount} messages discussing: ${topics || 'various topics'}`;
  }
  
  /**
   * Clean up old conversations in memory
   */
  private cleanupOldConversations() {
    if (this.memoryStore.size > 100) {
      const conversations = Array.from(this.memoryStore.values())
        .sort((a, b) => a.updatedAt.getTime() - b.updatedAt.getTime());
      
      // Remove oldest 20 conversations
      conversations.slice(0, 20).forEach(conv => {
        this.memoryStore.delete(conv.id);
      });
    }
  }
  
  /**
   * Helper to generate unique IDs
   */
  private generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }
  
  /**
   * Deserialize conversation from storage
   */
  private deserializeConversation(data: any): ConversationState {
    return {
      ...data,
      createdAt: new Date(data.created_at || data.createdAt),
      updatedAt: new Date(data.updated_at || data.updatedAt),
      messages: data.messages || [],
      context: {
        ...data.context,
        startedAt: new Date(data.context?.startedAt || Date.now()),
        lastActive: new Date(data.context?.lastActive || Date.now())
      }
    };
  }
}

// Singleton instance
let stateManager: AgentStateManager | null = null;

/**
 * Get or create state manager instance
 */
export function getStateManager(backend?: StorageBackend): AgentStateManager {
  if (!stateManager) {
    // Determine best backend based on environment
    let selectedBackend = backend;
    
    if (!selectedBackend) {
      if (process.env.UPSTASH_REDIS_REST_URL) {
        selectedBackend = StorageBackend.REDIS;
      } else if (process.env.NEXT_PUBLIC_SUPABASE_URL) {
        selectedBackend = StorageBackend.SUPABASE;
      } else {
        selectedBackend = StorageBackend.MEMORY;
      }
    }
    
    stateManager = new AgentStateManager(selectedBackend);
  }
  
  return stateManager;
}

// Export convenience functions
export async function startConversation(userId?: string): Promise<ConversationState> {
  return getStateManager().createConversation(userId);
}

export async function continueConversation(
  conversationId: string,
  message: Omit<AgentMessage, 'id' | 'timestamp'>
): Promise<AgentMessage> {
  return getStateManager().addMessage(conversationId, message);
}

export async function getConversationContext(conversationId: string): Promise<AgentContext | null> {
  return getStateManager().getContext(conversationId);
}

export async function updateConversationContext(
  conversationId: string,
  updates: Partial<AgentContext>
): Promise<void> {
  return getStateManager().updateContext(conversationId, updates);
}