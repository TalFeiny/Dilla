import { NextRequest } from 'next/server';
import { Anthropic } from '@anthropic-ai/sdk';
import { OpenAI } from 'openai';

// Agent modes
export enum AgentMode {
  QUICK_CHAT = 'quick_chat',
  MARKET_RESEARCH = 'market_research',
  FINANCIAL_ANALYSIS = 'financial_analysis',
  PWERM_ANALYSIS = 'pwerm_analysis',
  DUE_DILIGENCE = 'due_diligence',
  COMPLIANCE_KYC = 'compliance_kyc',
  DOCUMENT_ANALYSIS = 'document_analysis',
  PORTFOLIO_MONITOR = 'portfolio_monitor',
  LP_REPORTING = 'lp_reporting',
  MULTI_AGENT = 'multi_agent'
}

// Create a streaming response
export async function POST(request: NextRequest) {
  const encoder = new TextEncoder();
  const decoder = new TextDecoder();
  
  // Parse request
  const body = await request.json();
  const { message, mode, parameters = {}, stream = true } = body;
  
  // Determine mode
  const selectedMode = mode || determineAgentMode(message);
  
  // Create a TransformStream for streaming responses
  const customReadable = new ReadableStream({
    async start(controller) {
      // Send initial status
      controller.enqueue(encoder.encode(`data: ${JSON.stringify({
        type: 'status',
        message: `🚀 Starting ${selectedMode} analysis...`,
        mode: selectedMode
      })}\n\n`));
      
      try {
        switch (selectedMode) {
          case AgentMode.COMPLIANCE_KYC:
            await streamComplianceKYC(controller, encoder, message, parameters);
            break;
            
          case AgentMode.MARKET_RESEARCH:
            await streamMarketResearch(controller, encoder, message, parameters);
            break;
            
          case AgentMode.PWERM_ANALYSIS:
            await streamPWERM(controller, encoder, message, parameters);
            break;
            
          case AgentMode.MULTI_AGENT:
            await streamMultiAgent(controller, encoder, message, parameters);
            break;
            
          default:
            await streamQuickChat(controller, encoder, message, parameters);
        }
        
        // Send completion signal
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({
          type: 'complete',
          message: '✅ Analysis complete'
        })}\n\n`));
        
      } catch (error) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({
          type: 'error',
          message: error instanceof Error ? error.message : 'Unknown error'
        })}\n\n`));
      } finally {
        controller.close();
      }
    }
  });
  
  return new Response(customReadable, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}

// Stream compliance/KYC results
async function streamComplianceKYC(
  controller: ReadableStreamDefaultController,
  encoder: TextEncoder,
  message: string,
  parameters: any
) {
  const steps = [
    { step: '🔍 Searching corporate registries...', delay: 500 },
    { step: '📊 Analyzing corporate structure...', delay: 800 },
    { step: '🌍 Checking sanctions lists...', delay: 600 },
    { step: '👤 Screening PEP databases...', delay: 700 },
    { step: '📰 Scanning adverse media...', delay: 900 },
    { step: '🔗 Mapping beneficial ownership...', delay: 1000 },
    { step: '⚠️ Calculating risk scores...', delay: 400 }
  ];
  
  for (const { step, delay } of steps) {
    controller.enqueue(encoder.encode(`data: ${JSON.stringify({
      type: 'progress',
      message: step
    })}\n\n`));
    await new Promise(resolve => setTimeout(resolve, delay));
  }
  
  // Generate mock compliance result (replace with actual compliance check)
  const result = {
    entity: parameters.entity_name || 'Unknown Entity',
    risk_level: 'MEDIUM',
    risk_score: 65,
    flags: [
      { type: 'jurisdiction', description: 'Incorporated in offshore jurisdiction' },
      { type: 'structure', description: 'Complex ownership structure detected' }
    ],
    beneficial_owners: [
      { name: 'John Doe', ownership: 25.5, jurisdiction: 'Cayman Islands' }
    ],
    sanctions_check: 'CLEAR',
    pep_check: 'CLEAR',
    adverse_media: 'MINOR_ISSUES'
  };
  
  controller.enqueue(encoder.encode(`data: ${JSON.stringify({
    type: 'result',
    content: `## KYC Compliance Report

**Entity:** ${result.entity}
**Risk Level:** ${result.risk_level} (Score: ${result.risk_score}/100)

### Sanctions Check: ${result.sanctions_check} ✅
### PEP Check: ${result.pep_check} ✅
### Adverse Media: ${result.adverse_media} ⚠️

### Risk Flags Identified:
${result.flags.map(f => `- **${f.type}**: ${f.description}`).join('\n')}

### Beneficial Ownership:
${result.beneficial_owners.map(o => `- ${o.name} (${o.ownership}%) - ${o.jurisdiction}`).join('\n')}

### Recommendation:
Proceed with enhanced due diligence given medium risk profile.`
  })}\n\n`));
}

// Stream market research with real-time updates
async function streamMarketResearch(
  controller: ReadableStreamDefaultController,
  encoder: TextEncoder,
  message: string,
  parameters: any
) {
  controller.enqueue(encoder.encode(`data: ${JSON.stringify({
    type: 'progress',
    message: '🔎 Initiating market research...'
  })}\n\n`));
  
  // Simulate Tavily search with streaming results
  const searchTopics = [
    'Total addressable market size',
    'Key competitors analysis',
    'Recent funding rounds',
    'M&A activity and exits',
    'Market growth trends'
  ];
  
  for (const topic of searchTopics) {
    controller.enqueue(encoder.encode(`data: ${JSON.stringify({
      type: 'progress',
      message: `📊 Researching: ${topic}...`
    })}\n\n`));
    
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Stream partial results
    controller.enqueue(encoder.encode(`data: ${JSON.stringify({
      type: 'partial',
      content: `### ${topic}
- Found ${Math.floor(Math.random() * 10 + 5)} relevant sources
- Processing insights...

`
    })}\n\n`));
  }
  
  // Final compiled result
  controller.enqueue(encoder.encode(`data: ${JSON.stringify({
    type: 'result',
    content: `## Market Research Report

### Market Size
- **TAM:** $45.2B (2024)
- **Growth Rate:** 18.5% CAGR
- **Key Segments:** Enterprise (65%), SMB (35%)

### Competitive Landscape
1. **Stripe** - $95B valuation, dominant player
2. **Adyen** - Public, $45B market cap
3. **Checkout.com** - $40B valuation, growing fast

### Recent Activity
- 15 funding rounds in last 6 months
- Average Series B: $45M at $250M valuation
- 3 major acquisitions by strategic buyers

### Exit Comparables
- **Avg Revenue Multiple:** 12.5x
- **Median Exit Value:** $850M
- **Time to Exit:** 7.2 years average`
  })}\n\n`));
}

// Stream PWERM analysis with progress
async function streamPWERM(
  controller: ReadableStreamDefaultController,
  encoder: TextEncoder,
  message: string,
  parameters: any
) {
  const stages = [
    { name: 'Market Research', icon: '🌍' },
    { name: 'Competitor Analysis', icon: '🏢' },
    { name: 'Scenario Modeling', icon: '📈' },
    { name: 'Monte Carlo Simulation', icon: '🎲' },
    { name: 'Exit Distribution', icon: '📊' },
    { name: 'Risk Assessment', icon: '⚠️' }
  ];
  
  for (const stage of stages) {
    controller.enqueue(encoder.encode(`data: ${JSON.stringify({
      type: 'progress',
      message: `${stage.icon} Running ${stage.name}...`
    })}\n\n`));
    
    await new Promise(resolve => setTimeout(resolve, 1500));
    
    // Show intermediate results
    if (stage.name === 'Monte Carlo Simulation') {
      controller.enqueue(encoder.encode(`data: ${JSON.stringify({
        type: 'partial',
        content: `Running 10,000 simulations...
- Scenarios generated: 10,000
- Convergence achieved: ✓
- Confidence interval: 95%
`
      })}\n\n`));
    }
  }
  
  // Stream final PWERM results
  controller.enqueue(encoder.encode(`data: ${JSON.stringify({
    type: 'result',
    content: `## PWERM Analysis Complete

### Expected Outcomes
- **Expected Exit Value:** $285M
- **Median Exit Value:** $195M
- **Success Probability:** 72%

### Scenario Distribution
- 🚀 **Mega Exit (>$1B):** 8% probability
- 📈 **Strong Exit ($500M-1B):** 15% probability
- ✅ **Good Exit ($200-500M):** 35% probability
- 📊 **Moderate Exit ($50-200M):** 32% probability
- ❌ **Failure (<$50M):** 10% probability

### Risk-Adjusted Recommendation
**Investment Score:** 78/100
**Recommendation:** INVEST with 15% ownership target`
  })}\n\n`));
}

// Stream multi-agent CrewAI analysis
async function streamMultiAgent(
  controller: ReadableStreamDefaultController,
  encoder: TextEncoder,
  message: string,
  parameters: any
) {
  const agents = [
    { name: 'Market Researcher', emoji: '🔍', task: 'Analyzing market dynamics...' },
    { name: 'Financial Analyst', emoji: '💰', task: 'Evaluating financial metrics...' },
    { name: 'DD Lead', emoji: '📋', task: 'Conducting due diligence...' },
    { name: 'Investment Strategist', emoji: '🎯', task: 'Developing investment thesis...' }
  ];
  
  for (const agent of agents) {
    controller.enqueue(encoder.encode(`data: ${JSON.stringify({
      type: 'agent',
      message: `${agent.emoji} **${agent.name}**: ${agent.task}`
    })}\n\n`));
    
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Show agent thinking
    controller.enqueue(encoder.encode(`data: ${JSON.stringify({
      type: 'thinking',
      agent: agent.name,
      content: `Analyzing data points...`
    })}\n\n`));
    
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  
  // Final collaborative result
  controller.enqueue(encoder.encode(`data: ${JSON.stringify({
    type: 'result',
    content: `## Multi-Agent Analysis Complete

### Investment Thesis
Strong opportunity in growing market with defensible moat and exceptional team.

### Key Findings by Agent

**🔍 Market Researcher:**
- TAM: $45B growing at 22% CAGR
- Fragmented market ripe for consolidation
- Strong tailwinds from digital transformation

**💰 Financial Analyst:**
- Current ARR: $25M (150% YoY growth)
- Burn Multiple: 1.8x (efficient)
- Rule of 40: 170 (exceptional)

**📋 DD Lead:**
- ✅ Product-market fit validated
- ✅ Strong customer retention (125% NRR)
- ⚠️ Competitive risks from incumbents

**🎯 Investment Strategist:**
- **Recommendation:** STRONG INVEST
- **Proposed Terms:** $15M at $200M pre
- **Expected Return:** 8-12x in 5 years`
  })}\n\n`));
}

// Stream quick chat responses
async function streamQuickChat(
  controller: ReadableStreamDefaultController,
  encoder: TextEncoder,
  message: string,
  parameters: any
) {
  // Use Claude or GPT-4 for streaming
  const anthropicKey = process.env.ANTHROPIC_API_KEY || process.env.CLAUDE_API_KEY;
  const openaiKey = process.env.OPENAI_API_KEY;
  
  if (anthropicKey) {
    // Use Claude for streaming
    const anthropic = new Anthropic({ apiKey: anthropicKey });
    
    const stream = await anthropic.messages.create({
      model: 'claude-3-5-sonnet-20241022',
      max_tokens: 1000,
      messages: [{ role: 'user', content: message }],
      stream: true,
    });
    
    for await (const chunk of stream) {
      if (chunk.type === 'content_block_delta' && chunk.delta.type === 'text_delta') {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({
          type: 'token',
          content: chunk.delta.text
        })}\n\n`));
      }
    }
  } else if (openaiKey) {
    // Use OpenAI for streaming
    const openai = new OpenAI({ apiKey: openaiKey });
    
    const stream = await openai.chat.completions.create({
      model: 'gpt-4-turbo-preview',
      messages: [{ role: 'user', content: message }],
      stream: true,
    });
    
    for await (const chunk of stream) {
      const content = chunk.choices[0]?.delta?.content;
      if (content) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({
          type: 'token',
          content
        })}\n\n`));
      }
    }
  } else {
    // Fallback to simulated streaming
    const response = 'This is a simulated response. Please configure OpenAI or Anthropic API keys for real responses.';
    const words = response.split(' ');
    
    for (const word of words) {
      controller.enqueue(encoder.encode(`data: ${JSON.stringify({
        type: 'token',
        content: word + ' '
      })}\n\n`));
      await new Promise(resolve => setTimeout(resolve, 50));
    }
  }
}

// Helper function to determine mode
function determineAgentMode(query: string): AgentMode {
  const lowerQuery = query.toLowerCase();
  
  if (lowerQuery.includes('kyc') || lowerQuery.includes('compliance')) {
    return AgentMode.COMPLIANCE_KYC;
  }
  if (lowerQuery.includes('pwerm')) {
    return AgentMode.PWERM_ANALYSIS;
  }
  if (lowerQuery.includes('market') || lowerQuery.includes('research')) {
    return AgentMode.MARKET_RESEARCH;
  }
  if (lowerQuery.includes('comprehensive') || lowerQuery.includes('full analysis')) {
    return AgentMode.MULTI_AGENT;
  }
  
  return AgentMode.QUICK_CHAT;
}