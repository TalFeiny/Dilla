# Agent Matrix System - Multi-Step Reasoning & Model Building

## Overview
Enhanced Claude 3.5 agent system for building financial models with multi-step reasoning, clickable citations, and dynamic field searching in the matrix view.

## Core Components

### 1. Multi-Step Reasoning Engine

```typescript
interface ReasoningStep {
  step: number;
  action: 'search' | 'analyze' | 'calculate' | 'validate' | 'cite';
  query: string;
  result: any;
  sources: Citation[];
  confidence: number;
  nextSteps: string[];
}

interface Citation {
  text: string;
  url: string;
  title: string;
  relevance: number;
  timestamp: Date;
}
```

### 2. Model Building Pipeline

```typescript
class ModelBuilder {
  // Build models iteratively with citations
  async buildModel(company: string, modelType: string) {
    const steps = [];
    
    // Step 1: Gather base data
    steps.push(await this.searchCompanyData(company));
    
    // Step 2: Find comparables
    steps.push(await this.findComparables(company));
    
    // Step 3: Calculate metrics
    steps.push(await this.calculateMetrics(steps));
    
    // Step 4: Generate projections
    steps.push(await this.generateProjections(steps));
    
    // Step 5: Validate & cite
    steps.push(await this.validateWithCitations(steps));
    
    return this.assembleModel(steps);
  }
}
```

### 3. Citation System for Spreadsheet

```typescript
// Enhanced AgentDataGrid citation support
const agentAPI = {
  // Write with clickable citation
  writeCited: (cell: string, value: any, citation: Citation) => {
    grid.write(cell, value, {
      source: citation.title,
      sourceUrl: citation.url,
      href: citation.url
    });
  },
  
  // Create citation link in adjacent cell
  addCitation: (cell: string, citations: Citation[]) => {
    const citationText = citations.map((c, i) => `[${i+1}]`).join(' ');
    const firstUrl = citations[0]?.url;
    grid.link(cell, citationText, firstUrl);
  },
  
  // Write value with inline citation
  writeWithSource: (cell: string, value: any, source: string, url: string) => {
    grid.write(cell, `${value} [source]`, {
      href: url,
      source: source,
      sourceUrl: url
    });
  }
};
```

### 4. Dynamic Field Search (Fluid Field Names)

```typescript
class DynamicFieldMapper {
  private aliases = {
    revenue: ['revenue', 'sales', 'turnover', 'income', 'receipts'],
    profit: ['profit', 'earnings', 'net_income', 'ebitda', 'ebit'],
    growth: ['growth', 'growth_rate', 'cagr', 'yoy', 'increase'],
    valuation: ['valuation', 'market_cap', 'enterprise_value', 'ev'],
    funding: ['funding', 'investment', 'raised', 'capital', 'financing']
  };
  
  findField(data: any, fieldName: string): any {
    // Try exact match first
    if (data[fieldName]) return data[fieldName];
    
    // Try aliases
    const fieldLower = fieldName.toLowerCase();
    for (const [key, aliasList] of Object.entries(this.aliases)) {
      if (fieldLower.includes(key) || aliasList.some(a => fieldLower.includes(a))) {
        for (const alias of aliasList) {
          if (data[alias]) return data[alias];
        }
      }
    }
    
    // Try fuzzy match
    return this.fuzzyMatch(data, fieldName);
  }
}
```

## Implementation Strategy

### Phase 1: Enhanced Search & Citation

```python
# scripts/enhanced_agent_search.py
import asyncio
from typing import List, Dict, Any
from anthropic import Anthropic
from tavily import TavilyClient

class MultiStepReasoningAgent:
    def __init__(self):
        self.claude = Anthropic(api_key=os.getenv('CLAUDE_API_KEY'))
        self.tavily = TavilyClient(api_key=os.getenv('TAVILY_API_KEY'))
        self.reasoning_chain = []
        
    async def multi_step_search(self, query: str, max_steps: int = 5):
        """Execute multi-step reasoning with citations"""
        
        for step_num in range(max_steps):
            # Step 1: Plan next action
            action = await self.plan_next_action(query, self.reasoning_chain)
            
            # Step 2: Execute search
            if action['type'] == 'search':
                results = await self.search_with_citations(action['query'])
                
            # Step 3: Analyze results
            analysis = await self.analyze_results(results)
            
            # Step 4: Extract citations
            citations = self.extract_citations(results)
            
            # Step 5: Store reasoning step
            self.reasoning_chain.append({
                'step': step_num + 1,
                'action': action,
                'results': analysis,
                'citations': citations,
                'confidence': self.calculate_confidence(analysis)
            })
            
            # Check if we have enough information
            if self.is_complete(self.reasoning_chain):
                break
                
        return self.compile_final_answer(self.reasoning_chain)
    
    def extract_citations(self, results: List[Dict]) -> List[Dict]:
        """Extract clickable citations from search results"""
        citations = []
        for result in results:
            citations.append({
                'text': result.get('title', ''),
                'url': result.get('url', ''),
                'snippet': result.get('snippet', ''),
                'relevance': result.get('relevance_score', 0.5)
            })
        return citations
```

### Phase 2: Model Building Integration

```typescript
// src/lib/model-building-agent.ts
export class ModelBuildingAgent {
  private reasoning: ReasoningStep[] = [];
  
  async buildFinancialModel(company: string) {
    // Step 1: Search for company fundamentals
    const fundamentals = await this.searchAndCite(
      `${company} revenue earnings financial statements`,
      'fundamentals'
    );
    
    // Step 2: Find industry comparables
    const comparables = await this.searchAndCite(
      `${company} competitors industry comparables market share`,
      'comparables'
    );
    
    // Step 3: Get market data
    const marketData = await this.searchAndCite(
      `${company} sector TAM growth rate market trends`,
      'market'
    );
    
    // Step 4: Build the model
    return this.assembleModel({
      fundamentals,
      comparables,
      marketData
    });
  }
  
  private async searchAndCite(query: string, category: string) {
    const response = await fetch('/api/agent/search', {
      method: 'POST',
      body: JSON.stringify({ query, category })
    });
    
    const data = await response.json();
    
    // Store citations for each data point
    this.reasoning.push({
      step: this.reasoning.length + 1,
      action: 'search',
      query,
      result: data.results,
      sources: data.citations,
      confidence: data.confidence,
      nextSteps: data.suggestedActions
    });
    
    return data;
  }
  
  private assembleModel(data: any) {
    // Write to grid with citations
    const grid = (window as any).grid;
    
    // Headers
    grid.write('A1', 'Metric');
    grid.write('B1', 'Value');
    grid.write('C1', 'Source');
    
    // Write data with citations
    let row = 2;
    
    // Revenue
    if (data.fundamentals.revenue) {
      grid.write(`A${row}`, 'Revenue');
      grid.write(`B${row}`, data.fundamentals.revenue.value);
      grid.link(`C${row}`, '[1]', data.fundamentals.revenue.sourceUrl);
      row++;
    }
    
    // Growth Rate
    if (data.marketData.growthRate) {
      grid.write(`A${row}`, 'Market Growth');
      grid.write(`B${row}`, data.marketData.growthRate.value);
      grid.link(`C${row}`, '[2]', data.marketData.growthRate.sourceUrl);
      row++;
    }
    
    // Add comparables
    grid.write(`A${row + 1}`, 'Comparables');
    data.comparables.companies.forEach((comp, i) => {
      grid.write(`A${row + 2 + i}`, comp.name);
      grid.write(`B${row + 2 + i}`, comp.valuation);
      grid.link(`C${row + 2 + i}`, '[source]', comp.sourceUrl);
    });
    
    return { success: true, rows: row + data.comparables.companies.length };
  }
}
```

### Phase 3: Vectorization Strategy (Optional)

```python
# scripts/vector_store_manager.py
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
import numpy as np

class VectorStoreManager:
    """
    Vectorization for:
    1. Semantic search across company data
    2. Finding similar companies
    3. Caching frequent queries
    """
    
    def __init__(self):
        self.embeddings = OpenAIEmbeddings()
        self.vector_store = Chroma(
            collection_name="company_data",
            embedding_function=self.embeddings
        )
        
    def add_company_data(self, company: str, data: dict, citations: list):
        """Store company data with citations in vector DB"""
        
        # Create document with metadata
        document = {
            'text': f"{company}: {json.dumps(data)}",
            'metadata': {
                'company': company,
                'citations': citations,
                'timestamp': datetime.now().isoformat(),
                'data_type': 'financial'
            }
        }
        
        # Add to vector store
        self.vector_store.add_documents([document])
        
    def semantic_search(self, query: str, k: int = 5):
        """Find relevant data using semantic search"""
        
        results = self.vector_store.similarity_search_with_score(
            query=query,
            k=k
        )
        
        # Extract citations from metadata
        cited_results = []
        for doc, score in results:
            cited_results.append({
                'content': doc.page_content,
                'citations': doc.metadata.get('citations', []),
                'relevance': float(score),
                'company': doc.metadata.get('company')
            })
            
        return cited_results
```

## API Endpoints

```typescript
// src/app/api/agent/route.ts
export async function POST(request: Request) {
  const { action, params } = await request.json();
  
  switch (action) {
    case 'multi_step_reasoning':
      return handleMultiStepReasoning(params);
      
    case 'build_model':
      return handleModelBuilding(params);
      
    case 'search_with_citations':
      return handleCitedSearch(params);
      
    case 'dynamic_field_search':
      return handleDynamicFieldSearch(params);
  }
}

async function handleMultiStepReasoning({ query, maxSteps }) {
  const agent = new MultiStepReasoningAgent();
  const steps = [];
  
  for (let i = 0; i < maxSteps; i++) {
    const step = await agent.executeStep(query, steps);
    steps.push(step);
    
    if (step.isComplete) break;
  }
  
  return NextResponse.json({
    steps,
    finalAnswer: agent.compileFinalAnswer(steps),
    citations: agent.extractAllCitations(steps)
  });
}
```

## Usage Examples

### 1. Multi-Step Company Analysis
```javascript
// In browser console or agent interface
const agent = new ModelBuildingAgent();

// Analyze company with multi-step reasoning
await agent.analyze('Stripe', {
  steps: [
    'search_fundamentals',
    'find_comparables', 
    'calculate_valuation',
    'project_growth',
    'cite_sources'
  ]
});

// Results appear in grid with clickable citations
```

### 2. Dynamic Field Search
```javascript
// Search with fluid field names
grid.dynamicSearch('revenue', 'Stripe');  // Finds: revenue, sales, turnover
grid.dynamicSearch('profit', 'Airbnb');   // Finds: earnings, net_income, ebitda
grid.dynamicSearch('growth', 'Uber');     // Finds: growth_rate, cagr, yoy
```

### 3. Building Models with Citations
```javascript
// Build complete financial model
const model = await agent.buildFinancialModel('Databricks');

// Each cell in spreadsheet has:
// - Value (from search)
// - Clickable [source] link
// - Confidence score
// - Timestamp
```

## Performance Optimization

### Without Vectorization
- Direct API calls to Claude 3.5 and Tavily
- ~2-3 seconds per search
- Good for real-time, fresh data

### With Vectorization (Recommended for scale)
- Cache frequent searches
- Semantic similarity matching
- <100ms for cached queries
- Reduces API costs by 60-70%

## Cost Estimates

### Per Analysis (without vectorization)
- Claude 3.5: ~$0.05 per multi-step analysis
- Tavily: ~$0.02 per search
- Total: ~$0.15-0.25 per complete model

### With Vectorization
- Initial indexing: ~$10 for 10k companies
- Ongoing: ~$0.05 per new analysis
- 70% queries served from cache

## Next Steps

1. **Implement Phase 1**: Enhanced search with citations (1-2 days)
2. **Test citation display**: Ensure clickable links work in grid (few hours)
3. **Add multi-step logic**: Chain reasoning steps (1 day)
4. **Optional vectorization**: Add if volume > 100 queries/day
5. **Optimize prompts**: Fine-tune for financial analysis

## Key Benefits

- **Transparency**: Every data point has a clickable source
- **Multi-step reasoning**: Builds complex models iteratively
- **Dynamic fields**: Handles varying data structures
- **Cost-effective**: Caching reduces API calls
- **Agent-friendly**: Clean API for automation