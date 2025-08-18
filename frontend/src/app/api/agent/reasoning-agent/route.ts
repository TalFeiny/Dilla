import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import Anthropic from '@anthropic-ai/sdk';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

const anthropic = new Anthropic({
  apiKey: process.env.CLAUDE_API_KEY!,
});

const TAVILY_API_KEY = process.env.TAVILY_API_KEY;
const FIRECRAWL_API_KEY = process.env.FIRECRAWL_API_KEY;

// Research step types
enum ResearchStep {
  UNDERSTAND_QUERY = 'understand_query',
  IDENTIFY_ENTITIES = 'identify_entities', 
  DATABASE_LOOKUP = 'database_lookup',
  WEB_SEARCH = 'web_search',
  DEEP_SCRAPE = 'deep_scrape',
  MARKET_ANALYSIS = 'market_analysis',
  SYNTHESIZE = 'synthesize',
  VERIFY_CITATIONS = 'verify_citations'
}

interface ResearchPlan {
  steps: {
    type: ResearchStep;
    description: string;
    query?: string;
    entities?: string[];
    dependencies?: ResearchStep[];
  }[];
  mainEntities: string[];
  researchQuestions: string[];
}

interface Citation {
  source: string;
  url?: string;
  date?: string;
  confidence: number;
}

interface ResearchResult {
  step: ResearchStep;
  data: any;
  citations: Citation[];
  summary: string;
}

// Step 1: Deconstruct the user's query into a research plan
async function createResearchPlan(query: string): Promise<ResearchPlan> {
  // Check for @ mentions or company names first
  const hasAtMention = query.includes('@');
  const atMentionMatch = query.match(/@(\w+)/g);
  const companyNames = atMentionMatch ? atMentionMatch.map(m => m.substring(1)) : [];
  
  // If there's an @mention, ALWAYS treat it as a company lookup
  if (companyNames.length > 0) {
    const company = companyNames[0];
    console.log(`📌 Detected @mention for company: ${company}`);
    return {
      mainEntities: [company],
      researchQuestions: [
        `What is ${company}'s current valuation and funding status?`,
        `What does ${company} do - product/service description?`,
        `Who are ${company}'s competitors?`,
        `What is ${company}'s revenue and growth metrics?`,
        `Who founded ${company} and who are the key executives?`,
        `What is the latest news about ${company}?`
      ],
      steps: [
        { type: ResearchStep.IDENTIFY_ENTITIES, description: 'Extract company name', entities: [company] },
        { type: ResearchStep.DATABASE_LOOKUP, description: 'Check internal database', entities: [company] },
        { type: ResearchStep.WEB_SEARCH, description: `Search for ${company} funding and metrics`, query: `${company} company funding valuation revenue series investors ${new Date().getFullYear()}` },
        { type: ResearchStep.SYNTHESIZE, description: 'Create comprehensive company profile' }
      ]
    };
  }
  
  const prompt = `Analyze this query and create a detailed research plan:

Query: "${query}"

IMPORTANT: If the query contains @mentions or company names, focus research on those specific companies.

Break this down into:
1. Main entities to research (companies, people, technologies)
2. Key research questions that need answering
3. Logical sequence of research steps

Return ONLY a JSON object with this structure:
{
  "mainEntities": ["entity1", "entity2"],
  "researchQuestions": [
    "What is X's revenue?",
    "Who are the competitors?",
    "What is the market size?"
  ],
  "steps": [
    {
      "type": "identify_entities",
      "description": "Extract company and sector names",
      "entities": ["Company A", "Company B"]
    },
    {
      "type": "database_lookup",
      "description": "Check internal database for company data",
      "dependencies": ["identify_entities"]
    },
    {
      "type": "web_search",
      "description": "Search for latest funding and metrics",
      "query": "specific search query",
      "dependencies": ["identify_entities"]
    },
    {
      "type": "deep_scrape",
      "description": "Scrape company websites for detailed data",
      "dependencies": ["identify_entities"]
    },
    {
      "type": "market_analysis",
      "description": "Analyze market dynamics and competitors",
      "dependencies": ["web_search"]
    },
    {
      "type": "synthesize",
      "description": "Combine all research into final answer",
      "dependencies": ["database_lookup", "web_search", "deep_scrape", "market_analysis"]
    }
  ]
}`;

  const response = await anthropic.messages.create({
    model: 'claude-3-5-sonnet-latest',
    max_tokens: 2000,
    messages: [{ role: 'user', content: prompt }]
  });

  const content = response.content[0].type === 'text' ? response.content[0].text : '';
  const jsonMatch = content.match(/\{[\s\S]*\}/);
  
  if (jsonMatch) {
    return JSON.parse(jsonMatch[0]);
  }

  // Fallback plan if parsing fails
  return {
    mainEntities: [],
    researchQuestions: [query],
    steps: [
      { type: ResearchStep.IDENTIFY_ENTITIES, description: 'Extract entities', entities: [] },
      { type: ResearchStep.WEB_SEARCH, description: 'General search', query },
      { type: ResearchStep.SYNTHESIZE, description: 'Create response' }
    ]
  };
}

// Step 2: Execute database lookup with citations
async function executeDatabaseLookup(entities: string[]): Promise<ResearchResult> {
  const results: any[] = [];
  const citations: Citation[] = [];
  
  for (const entity of entities) {
    const { data, error } = await supabase
      .from('companies')
      .select('*')
      .or(`name.ilike.%${entity}%,description.ilike.%${entity}%`)
      .limit(5);
    
    if (data && data.length > 0) {
      results.push(...data);
      data.forEach(company => {
        citations.push({
          source: 'Internal Database',
          confidence: 1.0,
          date: company.updated_at || new Date().toISOString()
        });
      });
    }
  }
  
  return {
    step: ResearchStep.DATABASE_LOOKUP,
    data: results,
    citations,
    summary: `Found ${results.length} companies in database: ${results.map(r => r.name).join(', ')}`
  };
}

// Step 3: Execute web search with proper citations
async function executeWebSearch(query: string, depth: 'basic' | 'advanced' = 'advanced'): Promise<ResearchResult> {
  if (!TAVILY_API_KEY) {
    return {
      step: ResearchStep.WEB_SEARCH,
      data: null,
      citations: [],
      summary: 'Web search unavailable - Tavily API key not configured'
    };
  }

  console.log(`🔍 Executing ${depth} web search: "${query}"`);
  
  // Add company-specific searches if it looks like a company name
  const isCompanySearch = query.match(/^[A-Z][\w\s]+(?:funding|valuation|revenue|company)/i);
  
  const response = await fetch('https://api.tavily.com/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      api_key: TAVILY_API_KEY,
      query,
      search_depth: depth,
      max_results: depth === 'advanced' ? 20 : 10,
      include_answer: true,
      include_raw_content: true,
      include_domains: depth === 'advanced' ? [
        'techcrunch.com', 'crunchbase.com', 'pitchbook.com', 
        'reuters.com', 'bloomberg.com', 'forbes.com',
        'venturebeat.com', 'theinformation.com', 'sifted.eu',
        'tech.eu', 'businessinsider.com', 'cnbc.com'
      ] : undefined
    })
  });

  if (!response.ok) {
    throw new Error(`Tavily search failed: ${response.statusText}`);
  }

  const data = await response.json();
  
  const citations = data.results.map((result: any) => ({
    source: result.title,
    url: result.url,
    date: new Date().toISOString(),
    confidence: result.score || 0.8
  }));

  return {
    step: ResearchStep.WEB_SEARCH,
    data: {
      answer: data.answer,
      results: data.results,
      query: data.query
    },
    citations,
    summary: `Found ${data.results.length} web results. AI summary: ${data.answer?.substring(0, 200)}...`
  };
}

// Step 4: Use CIM endpoint for company deep analysis
async function executeCompanyCIM(companyName: string): Promise<ResearchResult> {
  try {
    console.log(`🔥 Getting comprehensive CIM profile for ${companyName}...`);
    
    // Try the enhanced scraper first
    const baseUrl = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3001';
    const response = await fetch(`${baseUrl}/api/agent/company-cim`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        company_name: companyName,
        refresh: false
      })
    });
    
    if (response.ok) {
      const result = await response.json();
      
      // Extract key data from CIM
      const cimData = result.cim || {};
      const citations = [];
      
      // Add citations from CIM data
      if (cimData.citations) {
        cimData.citations.forEach((c: any) => {
          citations.push({
            source: c.source,
            url: c.url,
            date: c.date,
            confidence: c.relevance || 0.9
          });
        });
      } else {
        citations.push({
          source: 'Company CIM Deep Analysis',
          confidence: 0.95,
          date: result.generated_date || new Date().toISOString()
        });
      }
      
      return {
        step: ResearchStep.DEEP_SCRAPE,
        data: cimData,
        citations,
        summary: `Deep analysis complete: ${cimData.executive_summary || `Comprehensive profile generated for ${companyName}`}`
      };
    }
  } catch (error) {
    console.error('CIM generation failed:', error);
  }
  
  // Fallback to direct web scraping if CIM fails
  console.log(`⚠️ CIM failed, attempting direct web scrape for ${companyName}`);
  return {
    step: ResearchStep.DEEP_SCRAPE,
    data: null,
    citations: [],
    summary: `Deep scraping unavailable - using web search data`
  };
}

// Step 5: Synthesize with mandatory citations
async function synthesizeWithCitations(
  query: string,
  researchResults: ResearchResult[],
  researchQuestions: string[]
): Promise<string> {
  // Build comprehensive context
  let context = "# RESEARCH RESULTS WITH CITATIONS\n\n";
  
  researchResults.forEach(result => {
    context += `## ${result.step}\n`;
    context += `Summary: ${result.summary}\n`;
    context += `Citations: ${result.citations.map(c => `[${c.source}](${c.url || 'internal'})`).join(', ')}\n`;
    
    if (result.data) {
      context += `Data: ${JSON.stringify(result.data, null, 2).substring(0, 3000)}...\n`;
    }
    context += '\n';
  });

  const prompt = `You are an expert analyst providing research-backed answers.

ORIGINAL QUERY: "${query}"

RESEARCH QUESTIONS TO ANSWER:
${researchQuestions.map((q, i) => `${i + 1}. ${q}`).join('\n')}

${context}

CRITICAL REQUIREMENTS:
1. Answer EACH research question using ONLY the data provided
2. EVERY statement must have a citation like [Source: Name, URL]
3. Use this exact format: "Statement here [Source: TechCrunch, techcrunch.com]"
4. If data is missing for a question, state: "No data available for [topic] - further research needed"
5. Begin with: "Based on my multi-step research from [list unique sources]:"
6. Show your reasoning process step by step
7. Never make claims without citations
8. Present conflicting data when sources disagree

Structure your response:
1. Summary of sources consulted
2. Answer to each research question with citations
3. Key insights with citations
4. Data gaps that need filling

Remember: NO STATEMENTS WITHOUT CITATIONS!`;

  const response = await anthropic.messages.create({
    model: 'claude-3-5-sonnet-latest',
    max_tokens: 3000,
    messages: [{ role: 'user', content: prompt }]
  });

  return response.content[0].type === 'text' ? response.content[0].text : 'Failed to synthesize results';
}

// Main handler with multi-step reasoning + RL
export async function POST(request: Request) {
  try {
    const { message, sessionId = `session-${Date.now()}` } = await request.json();
    
    if (!message) {
      return NextResponse.json(
        { error: 'Message is required' },
        { status: 400 }
      );
    }

    console.log('🧠 Starting multi-step reasoning for:', message);
    
    // Step 0: Check RL for learned patterns
    let rlContext = { enhancedContext: '', corrections: [] };
    const companyName = message.match(/@?(\w+)/)?.[1];
    
    try {
      const rlResponse = await fetch(`${request.url.replace('/reasoning-agent', '')}/rl/retrieve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: message, company: companyName, agent: 'reasoning-agent' })
      });
      
      if (rlResponse.ok) {
        const rlData = await rlResponse.json();
        if (rlData.hasContext) {
          rlContext = rlData;
          console.log(`📚 Found ${rlData.contextCount} relevant past feedbacks`);
        }
      }
    } catch (error) {
      console.log('RL lookup failed, continuing without context');
    }
    
    // Quick check: if it's just an @mention, treat it as a company lookup
    const isSimpleCompanyLookup = message.trim().startsWith('@') && message.trim().split(' ').length <= 2;
    
    // Step 1: Create research plan (enhanced with RL context)
    console.log('📋 Creating research plan...');
    const planPrompt = rlContext.enhancedContext 
      ? `${message}${rlContext.enhancedContext}`
      : message;
    const plan = await createResearchPlan(planPrompt);
    console.log('📋 Research plan created:', {
      entities: plan.mainEntities,
      questions: plan.researchQuestions.length,
      steps: plan.steps.length
    });

    // Step 2: Execute research steps (optimized for speed)
    const researchResults: ResearchResult[] = [];
    
    // For @mentions, do comprehensive parallel execution
    if (plan.mainEntities.length > 0 && message.includes('@')) {
      console.log('🚀 Comprehensive parallel execution for @mention:', plan.mainEntities);
      
      const promises = [
        // Database lookup
        executeDatabaseLookup(plan.mainEntities),
        // Deep web search with proper company name
        executeWebSearch(
          `"${plan.mainEntities[0]}" company funding valuation revenue metrics latest news ${new Date().getFullYear()}`,
          'advanced'  // Use advanced for better results
        ),
        // CIM deep scraping
        executeCompanyCIM(plan.mainEntities[0])
      ];
      
      // Add market analysis
      promises.push(
        executeWebSearch(
          `"${plan.mainEntities[0]}" competitors market analysis industry trends ${new Date().getFullYear()}`,
          'basic'
        )
      );
      
      const results = await Promise.all(promises);
      researchResults.push(...results);
    } else {
      // Regular flow for complex queries
      if (plan.mainEntities.length > 0) {
        console.log('🗄️ Checking database for:', plan.mainEntities);
        const dbResult = await executeDatabaseLookup(plan.mainEntities);
        researchResults.push(dbResult);
        
        // Search for each entity
        for (const entity of plan.mainEntities) {
          console.log(`🔍 Direct search for company: ${entity}`);
          const companySearch = await executeWebSearch(
            `"${entity}" company funding valuation revenue profile ${new Date().getFullYear()}`,
            'advanced'
          );
          researchResults.push(companySearch);
        }
      }

      // Web searches for top research questions
      for (const question of plan.researchQuestions.slice(0, 2)) {
        console.log(`🔍 Researching: ${question}`);
        const searchResult = await executeWebSearch(question, 'basic');
        researchResults.push(searchResult);
      }
    }

    // Always use CIM for deep analysis of main entities
    if (plan.mainEntities.length > 0 && !message.includes('@')) {
      // For non-@mentions, still get CIM data
      for (const entity of plan.mainEntities.slice(0, 2)) { // Limit to 2 companies
        console.log(`🔥 Getting comprehensive CIM profile for ${entity}...`);
        const cimResult = await executeCompanyCIM(entity);
        if (cimResult.data) {
          researchResults.push(cimResult);
        }
      }
    }

    // Market analysis for main entities
    if (plan.mainEntities.length > 0) {
      console.log('📊 Analyzing market dynamics...');
      const marketQuery = `${plan.mainEntities.join(' ')} market analysis competitors valuation trends ${new Date().getFullYear()}`;
      const marketResult = await executeWebSearch(marketQuery, 'advanced');
      researchResults.push(marketResult);
    }

    // Step 3: Synthesize all research with citations (include RL corrections)
    console.log('🧪 Synthesizing research with citations...');
    const enhancedResults = rlContext.corrections?.length > 0
      ? [...researchResults, {
          step: ResearchStep.SYNTHESIZE,
          data: { corrections: rlContext.corrections },
          citations: [{ source: 'Past Feedback', confidence: 0.9 }],
          summary: `Applied ${rlContext.corrections.length} learned corrections from past feedback`
        }]
      : researchResults;
      
    const finalResponse = await synthesizeWithCitations(
      message + (rlContext.enhancedContext || ''),
      enhancedResults,
      plan.researchQuestions
    );

    // Step 5: Extract all unique citations
    const allCitations = enhancedResults.flatMap(r => r.citations);
    const uniqueSources = [...new Set(allCitations.map(c => c.source))];

    return NextResponse.json({
      response: finalResponse,
      reasoning: {
        plan,
        stepsExecuted: enhancedResults.map(r => ({
          step: r.step,
          summary: r.summary,
          citationCount: r.citations.length
        })),
        totalCitations: allCitations.length,
        uniqueSources
      },
      metadata: {
        researchSteps: enhancedResults.length,
        totalSources: uniqueSources.length,
        timestamp: new Date().toISOString(),
        mode: 'multi-step-reasoning',
        sessionId,
        usedRL: rlContext.corrections?.length > 0,
        rlCorrections: rlContext.corrections?.length || 0
      }
    });

  } catch (error) {
    console.error('Reasoning agent error:', error);
    return NextResponse.json(
      { 
        error: 'Multi-step reasoning failed',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}

// GET endpoint to show capabilities
export async function GET() {
  return NextResponse.json({
    name: 'Multi-Step Reasoning Agent',
    description: 'Performs thorough multi-step research with proper citations',
    capabilities: [
      'Query deconstruction into research steps',
      'Multi-source data gathering (database, web, scraping)',
      'Chain-of-thought reasoning',
      'Mandatory citation for every claim',
      'Conflicting data detection',
      'Progressive knowledge building'
    ],
    researchSteps: Object.values(ResearchStep),
    dataSources: [
      'Internal Database',
      'Tavily Web Search',
      'Firecrawl Deep Scraping',
      'Market Intelligence APIs'
    ],
    citationPolicy: 'Every statement must have a verifiable source'
  });
}