import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { getBestRoute } from '../feedback/route';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

// Context management
interface SessionContext {
  session_id: string;
  company?: string;
  sector?: string;
  companies?: string[];
  
  // Cached data
  company_data?: any;
  market_data?: any;
  world_model?: any;
  comparables?: any[];
  valuations?: Record<string, any>;
  
  // Conversation state
  messages: Array<{
    role: string;
    content: string;
    metadata?: any;
  }>;
  intent_history: string[];
  last_intent?: string;
  last_analysis?: any;
}

// Intent detection with clear mappings
const INTENT_MAPPINGS = {
  // Data fetching
  'get_company_data': {
    keywords: ['revenue', 'funding', 'metrics', 'financials', 'valuation'],
    endpoint: '/api/agent/data-sources',
    cacheable: true
  },
  'get_market_data': {
    keywords: ['market size', 'tam', 'sam', 'som', 'market'],
    endpoint: '/api/agent/enhanced-data-pipeline',
    cacheable: true
  },
  
  // Analysis
  'valuation': {
    keywords: ['value', 'valuation', 'worth', 'price'],
    endpoint: '/api/agent/ipev-valuation',
    requires: ['company_data']
  },
  'pwerm': {
    keywords: ['pwerm', 'probability weighted', 'exit scenarios'],
    endpoint: '/api/pwerm-analysis',
    requires: ['company_data', 'market_data']
  },
  'comparison': {
    keywords: ['compare', 'versus', 'vs', 'comparison', 'difference'],
    endpoint: '/api/agent/multi-analysis',
    requires: ['companies']
  },
  'business_model': {
    keywords: ['business model', 'revenue model', 'monetization', 'unit economics'],
    endpoint: '/api/agent/multi-analysis',
    requires: ['company_data']
  },
  
  // World model
  'world_model': {
    keywords: ['market analysis', 'competitive landscape', 'industry', 'sector analysis'],
    endpoint: '/api/agent/world-model',
    cacheable: true
  },
  
  // Synthesis
  'investment_thesis': {
    keywords: ['investment', 'thesis', 'opportunity', 'recommendation', 'should invest'],
    endpoint: '/api/agent/multi-analysis',
    requires: ['company_data', 'market_data']
  }
};

class ContextManager {
  async get(sessionId: string): Promise<SessionContext> {
    const { data } = await supabase
      .from('agent_sessions')
      .select('*')
      .eq('session_id', sessionId)
      .single();

    if (data) {
      return data.context as SessionContext;
    }

    // Create new session
    return {
      session_id: sessionId,
      messages: [],
      intent_history: []
    };
  }

  async update(sessionId: string, updates: Partial<SessionContext>) {
    const current = await this.get(sessionId);
    const updated = { ...current, ...updates };

    await supabase
      .from('agent_sessions')
      .upsert({
        session_id: sessionId,
        context: updated,
        updated_at: new Date()
      });

    return updated;
  }

  async addMessage(sessionId: string, message: any) {
    const context = await this.get(sessionId);
    context.messages.push(message);
    
    if (message.metadata?.intent) {
      context.intent_history.push(message.metadata.intent);
      context.last_intent = message.metadata.intent;
    }

    await this.update(sessionId, context);
  }

  async cacheData(sessionId: string, dataType: string, data: any) {
    const updates: Partial<SessionContext> = {};
    updates[dataType] = data;
    await this.update(sessionId, updates);
  }
}

// Smart intent detection
function detectIntent(query: string, context: SessionContext): string {
  const lowerQuery = query.toLowerCase();

  // Check for follow-up patterns
  if (lowerQuery.includes('tell me more') || 
      lowerQuery.includes('what about') || 
      lowerQuery.includes('how about')) {
    // Use last intent as base
    return context.last_intent || 'investment_thesis';
  }

  // Check each intent's keywords
  for (const [intent, config] of Object.entries(INTENT_MAPPINGS)) {
    if (config.keywords.some(kw => lowerQuery.includes(kw))) {
      return intent;
    }
  }

  // Check for company names to extract
  if (lowerQuery.includes(' vs ') || lowerQuery.includes(' versus ')) {
    return 'comparison';
  }

  // Default to comprehensive analysis
  return 'investment_thesis';
}

// Extract entities from query
function extractEntities(query: string): any {
  const entities: any = {};

  // Better company name extraction patterns
  const companyPatterns = [
    // Match after keywords: "search for Stripe", "find Stripe", etc
    /(?:search\s+for|find|about|analyze|compare|get|fetch|lookup|information\s+about|info\s+on|data\s+for)\s+([A-Z][a-zA-Z0-9\.\-]+(?:\s+[A-Z]?[a-zA-Z0-9\.\-]+)*)/gi,
    // Match company names in quotes
    /["']([^"']+)["']/g,
    // Match standalone capitalized words/phrases (likely company names)
    /\b([A-Z][a-zA-Z0-9]+(?:[\.\-][a-zA-Z0-9]+)?(?:\s+[A-Z][a-zA-Z0-9]+)?)\b/g,
    // Match "X vs Y" pattern
    /\b([A-Z][a-zA-Z0-9]+)\s+(?:vs\.?|versus)\s+([A-Z][a-zA-Z0-9]+)/gi,
  ];
  
  const foundCompanies = new Set<string>();
  
  for (const pattern of companyPatterns) {
    const matches = query.matchAll(pattern);
    for (const match of matches) {
      // Handle vs/versus pattern which captures two groups
      if (match[2]) {
        foundCompanies.add(match[1].trim());
        foundCompanies.add(match[2].trim());
      } else if (match[1]) {
        const company = match[1].trim();
        // Filter out common words that aren't company names
        const excludeWords = ['The', 'For', 'About', 'Search', 'Find', 'Get', 'What', 'How', 'Why', 'When', 'Where'];
        if (!excludeWords.includes(company) && company.length > 2) {
          foundCompanies.add(company);
        }
      }
    }
  }
  
  const companiesArray = Array.from(foundCompanies);
  
  if (companiesArray.length === 1) {
    entities.company = companiesArray[0];
  } else if (companiesArray.length > 1) {
    entities.companies = companiesArray;
  }

  // Extract sector
  const sectors = ['SaaS', 'FinTech', 'AI', 'Healthcare', 'Marketplace', 'B2B', 'B2C', 'HR', 'Defense', 'Climate'];
  for (const sector of sectors) {
    if (query.toLowerCase().includes(sector.toLowerCase())) {
      entities.sector = sector;
      break;
    }
  }

  return entities;
}

// Check if we have required data in context
function hasRequiredData(context: SessionContext, requirements: string[]): boolean {
  if (!requirements) return true;
  
  for (const req of requirements) {
    if (!context[req]) return false;
  }
  
  return true;
}

// Route with optimization
async function routeWithOptimization(intent: string, context: SessionContext): Promise<string> {
  // Try to get optimized route based on feedback
  const optimizedRoute = await getBestRoute(intent);
  
  if (optimizedRoute) {
    console.log(`Using optimized route for ${intent}: ${optimizedRoute}`);
    return optimizedRoute;
  }

  // Fall back to default mapping
  const mapping = INTENT_MAPPINGS[intent];
  return mapping?.endpoint || '/api/agent/chat';
}

// Main orchestrator handler
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { message, sessionId = 'default' } = body;

    if (!message) {
      return NextResponse.json(
        { error: 'Message is required' },
        { status: 400 }
      );
    }

    // Get session context
    const contextManager = new ContextManager();
    const context = await contextManager.get(sessionId);

    // Detect intent
    const intent = detectIntent(message, context);
    console.log(`Detected intent: ${intent} for query: ${message}`);

    // Extract entities
    const entities = extractEntities(message);
    if (entities.company) context.company = entities.company;
    if (entities.companies) context.companies = entities.companies;
    if (entities.sector) context.sector = entities.sector;

    // Check if we have required data
    const intentConfig = INTENT_MAPPINGS[intent];
    if (intentConfig?.requires && !hasRequiredData(context, intentConfig.requires)) {
      // Need to fetch required data first
      console.log(`Fetching required data: ${intentConfig.requires}`);
      
      for (const req of intentConfig.requires) {
        if (!context[req]) {
          if (req === 'company_data' && context.company) {
            const dataRoute = await routeWithOptimization('get_company_data', context);
            const response = await fetch(`http://localhost:3001${dataRoute}`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ company: context.company })
            });
            const data = await response.json();
            await contextManager.cacheData(sessionId, 'company_data', data);
          }
          // Add other data fetching as needed
        }
      }
    }

    // Check cache for cacheable intents
    if (intentConfig?.cacheable && context[intent]) {
      console.log(`Using cached data for ${intent}`);
      return NextResponse.json({
        result: context[intent],
        metadata: {
          route_id: `${sessionId}-${Date.now()}`,
          intent,
          endpoint: 'cache',
          cached: true
        }
      });
    }

    // Route to appropriate endpoint
    const endpoint = await routeWithOptimization(intent, context);
    console.log(`Routing to: ${endpoint}`);

    // Prepare request with context
    const requestBody = {
      ...body,
      context: {
        company: context.company,
        sector: context.sector,
        companies: context.companies,
        company_data: context.company_data,
        market_data: context.market_data,
        world_model: context.world_model
      }
    };

    // Call the endpoint
    const startTime = Date.now();
    const response = await fetch(`http://localhost:3001${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody)
    });

    const result = await response.json();
    const responseTime = Date.now() - startTime;

    // Generate route ID for feedback tracking
    const routeId = `${sessionId}-${Date.now()}`;

    // Prepare metadata for feedback
    const metadata = {
      route_id: routeId,
      intent,
      endpoint,
      sources: result.sources || [],
      confidence: result.confidence || 0.7,
      response_time: responseTime
    };

    // Store message and response in context
    await contextManager.addMessage(sessionId, {
      role: 'user',
      content: message
    });

    await contextManager.addMessage(sessionId, {
      role: 'assistant',
      content: result,
      metadata
    });

    // Cache if appropriate
    if (intentConfig?.cacheable) {
      await contextManager.cacheData(sessionId, intent, result);
    }

    // Update last analysis
    await contextManager.update(sessionId, {
      last_analysis: result,
      last_intent: intent
    });

    return NextResponse.json({
      success: true,
      result,
      metadata,
      session_id: sessionId
    });

  } catch (error) {
    console.error('Orchestrator error:', error);
    return NextResponse.json(
      { 
        error: 'Orchestration failed',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}

// GET endpoint to view session context
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const sessionId = searchParams.get('sessionId');

  if (!sessionId) {
    return NextResponse.json(
      { error: 'Session ID required' },
      { status: 400 }
    );
  }

  const contextManager = new ContextManager();
  const context = await contextManager.get(sessionId);

  return NextResponse.json({
    session_id: sessionId,
    context,
    intent_history: context.intent_history,
    cached_data: {
      has_company_data: !!context.company_data,
      has_market_data: !!context.market_data,
      has_world_model: !!context.world_model
    }
  });
}