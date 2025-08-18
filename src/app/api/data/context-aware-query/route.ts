import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { ContextManager } from '@/lib/context-manager';
import { processSemanticQuery, toSQL, toWebSearchQuery } from '@/lib/semantic-query-processor';
import Anthropic from '@anthropic-ai/sdk';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

const anthropic = new Anthropic({
  apiKey: process.env.CLAUDE_API_KEY!,
});

// Global context managers (in production, use session-based storage)
const contextManagers = new Map<string, ContextManager>();

// Get or create context manager for session
function getContextManager(sessionId: string): ContextManager {
  if (!contextManagers.has(sessionId)) {
    contextManagers.set(sessionId, new ContextManager());
  }
  return contextManagers.get(sessionId)!;
}

// Main execution function
async function executeQuery(query: string, context: any) {
  // Process semantic query
  const structured = processSemanticQuery(query);
  
  // Parallel data fetching
  const promises = [];
  
  // Database query
  if (structured.sources.includes('database')) {
    promises.push(fetchFromDatabase(structured));
  }
  
  // Web search
  if (structured.sources.includes('web')) {
    promises.push(fetchFromWeb(structured));
  }
  
  // Wait for all sources
  const results = await Promise.all(promises);
  
  // Merge results
  return mergeResults(results, context);
}

async function fetchFromDatabase(structured: any) {
  try {
    let query = supabase.from('companies').select('*');
    
    // Apply filters
    if (structured.entities.companies?.length > 0) {
      query = query.in('name', structured.entities.companies);
    }
    
    const { data, error } = await query.limit(50);
    return { source: 'database', data: data || [] };
  } catch (error) {
    console.error('Database fetch error:', error);
    return { source: 'database', data: [] };
  }
}

async function fetchFromWeb(structured: any) {
  try {
    const webQuery = toWebSearchQuery(structured);
    
    const response = await fetch('https://api.tavily.com/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: process.env.TAVILY_API_KEY,
        query: webQuery,
        max_results: 5
      })
    });
    
    if (!response.ok) return { source: 'web', data: [] };
    
    const data = await response.json();
    return { source: 'web', data: data.results || [] };
  } catch (error) {
    console.error('Web fetch error:', error);
    return { source: 'web', data: [] };
  }
}

function mergeResults(results: any[], context: any) {
  const merged = {
    data: [],
    sources: {}
  };
  
  results.forEach(result => {
    if (result.data && result.data.length > 0) {
      merged.data.push(...result.data);
      merged.sources[result.source] = result.data.length;
    }
  });
  
  // If extending, merge with existing
  if (context?.mergeWith) {
    merged.data = [...(context.mergeWith.data || []), ...merged.data];
  }
  
  return merged;
}

// Use Claude for complex query understanding
async function understandComplexQuery(query: string, context: any) {
  const response = await anthropic.messages.create({
    model: 'claude-3-haiku-20240307',
    max_tokens: 500,
    temperature: 0,
    messages: [{
      role: 'user',
      content: `
Context:
- Currently showing: ${JSON.stringify(context.currentOutput?.type || 'nothing')}
- Known entities: ${Array.from(context.entities?.keys() || [])}
- Last operation: ${context.lastMentioned?.operation || 'none'}

User says: "${query}"

Analyze:
1. What is the user's intent? (override/extend/refine/compare/new)
2. What entities are referenced? (including pronouns)
3. What action should be taken?

Output JSON:
{
  "intent": "...",
  "entities": [...],
  "action": "...",
  "preserveContext": true/false
}
`
    }]
  });
  
  try {
    return JSON.parse(response.content[0].text);
  } catch {
    return { intent: 'new', entities: [], action: 'search' };
  }
}

export async function POST(request: NextRequest) {
  try {
    const { query, sessionId = 'default', contextData } = await request.json();
    
    // Get context manager for this session
    const contextManager = getContextManager(sessionId);
    
    // If context data provided, restore it
    if (contextData) {
      // Restore context from client
    }
    
    // Process query with context awareness
    const result = await contextManager.processQuery(query, executeQuery);
    
    // For complex queries, use Claude
    if (result.intent === 'compare' || result.intent === 'analyze') {
      const understanding = await understandComplexQuery(
        result.resolvedQuery,
        contextManager.getContext()
      );
      
      // Enhance result with Claude's understanding
      result.enhanced = understanding;
    }
    
    return NextResponse.json({
      success: true,
      ...result,
      sessionId
    });
    
  } catch (error) {
    console.error('Context-aware query error:', error);
    return NextResponse.json(
      { error: 'Failed to process query', details: error },
      { status: 500 }
    );
  }
}

// GET endpoint to retrieve current context
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const sessionId = searchParams.get('sessionId') || 'default';
  
  const contextManager = getContextManager(sessionId);
  
  return NextResponse.json({
    context: contextManager.getContext(),
    sessionId
  });
}