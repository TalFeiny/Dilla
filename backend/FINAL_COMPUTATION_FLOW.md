# Final Computation Flow: Raw Data → Analysis → Graphs

## Current Architecture

### 1. Entry Point
```python
# Frontend calls
POST /api/agent/unified-brain
{
    "prompt": "Compare @Ramp and @Brex for Series C",
    "output_format": "analysis"
}
```

### 2. Orchestrator Processing
```python
# unified_mcp_orchestrator.py
async def process_request():
    # Step 1: Extract companies
    entities = ["@Ramp", "@Brex"]
    
    # Step 2: Gather data (parallel)
    for company in entities:
        - Tavily search (general, pricing, customers)
        - GitHub momentum analysis
        - Website scraping
        - Funding history from DB
    
    # Step 3: Score companies (THIS IS WHERE WE ARE NOW)
    for company_data in companies_data:
        # Current scoring
        inferred = gap_filler.infer_from_funding_cadence()
        fund_fit = gap_filler.score_fund_fit()
        
        # NEW: Comprehensive analysis
        deal_analysis = await comprehensive_analyzer.analyze_deal(company_data)
```

### 3. Comprehensive Deal Analysis (NEW)
```python
# comprehensive_deal_analyzer.py
async def analyze_deal(company_data):
    # 1. AI & Momentum
    ai_analysis = gap_filler.analyze_ai_impact()  # Dynamic scoring
    momentum = gap_filler.analyze_company_momentum()  # Founding to now
    
    # 2. Market Analysis (with citations)
    market = {
        'tam': $40B,  # "IDC AI Infrastructure 2025"
        'growth': 85% CAGR,
        'capture': [0.1% Y1, 5% Y5],  # "Bessemer Cloud Index"
        'adjacent': ['MLOps +$10B', 'Data Tools +$30B']
    }
    
    # 3. Scenarios (AI-adjusted)
    scenarios = {
        'base': {
            'return': 5x,
            'probability': 50%,
            'revenue_5y': $500M,
            'exit_value': $5B
        },
        'bull': {
            'return': 10x if ai_winner else 5x,
            'probability': 30% if ai_winner else 15%
        },
        'bear': {
            'return': 0.5x if 2021_vintage else 0.8x,
            'probability': 40% if cost_center else 20%
        }
    }
    
    # 4. Cap Table Math
    ownership = {
        'initial': 10%,
        'diluted_no_participation': 6%,
        'diluted_with_prorata': 10%,
        'liquidation_preference': calculate_waterfall()
    }
    
    # 5. Generate Visualizations
    charts = generate_all_charts()
    
    return DealComparison(all_the_above)
```

### 4. Chart Generation
```python
def generate_all_charts():
    return {
        # 1. Scenario Returns (Bar Chart)
        'scenario_comparison': {
            'type': 'grouped_bar',
            'data': {
                'Base': [5x, 25% IRR],
                'Bull': [10x, 58% IRR],
                'Bear': [0.8x, -5% IRR]
            }
        },
        
        # 2. Market Capture Timeline (Line Chart)
        'market_capture': {
            'type': 'line',
            'data': {
                '2025': 0.1% = $40M,
                '2028': 1% = $600M,
                '2030': 5% = $2.5B
            }
        },
        
        # 3. Ownership Dilution (Waterfall)
        'dilution_waterfall': {
            'type': 'waterfall',
            'stages': ['Seed', 'A', 'B', 'C', 'Exit'],
            'ownership': [15%, 12%, 9%, 7%, 5%]
        },
        
        # 4. AI/Momentum Radar
        'competitive_position': {
            'type': 'radar',
            'axes': ['AI Score', 'Momentum', 'Market', 'Team', 'Product'],
            'values': [8, 7, 9, 6, 8]
        },
        
        # 5. Exit Waterfall by Preference
        'liquidation_analysis': {
            'type': 'stacked_bar',
            'scenarios': ['$100M', '$500M', '$1B', '$5B'],
            'distribution': [
                [100%, 0%, 0%],      # All to preferred
                [40%, 60%, 0%],      # Split
                [20%, 40%, 40%],     # All participate
                [10%, 30%, 60%]      # Common wins
            ]
        }
    }
```

### 5. Final Synthesis
```python
# Back in orchestrator
all_comparisons = [deal1, deal2, deal3...]

# Send to Claude for narrative
synthesis_prompt = f"""
Companies analyzed with scores:
1. @Ramp: Fund Fit 8.5, AI: Traditional, Market: $15B
2. @Brex: Fund Fit 7.8, AI: Emerging, Market: $15B

{all_comparisons_data}

Provide investment recommendation considering:
- AI impact on each company
- Market capture potential
- Down round risks
- Adjacent market opportunities
"""

claude_response = await claude.synthesize(synthesis_prompt)

# Return complete package
return {
    'analysis': claude_response,
    'data': all_comparisons,
    'visualizations': all_charts,
    'citations': all_citations
}
```

## What's Missing (Need to Wire)

1. **Call ComprehensiveDealAnalyzer from orchestrator**
```python
# In unified_mcp_orchestrator.py
from app.services.comprehensive_deal_analyzer import ComprehensiveDealAnalyzer

async def _analyze_companies(self, companies_data):
    analyzer = ComprehensiveDealAnalyzer()
    comparisons = []
    
    for company in companies_data:
        deal = await analyzer.analyze_deal(company)
        comparisons.append(deal)
    
    return comparisons
```

2. **Format charts for frontend consumption**
```python
# Charts need to match frontend chart libraries
def format_for_frontend(charts):
    return {
        'chartjs': convert_to_chartjs_format(charts),
        'recharts': convert_to_recharts_format(charts),
        'raw': charts  # For custom rendering
    }
```

3. **Ensure citations flow through**
```python
# Every data point needs source
market_data = {
    'value': $40B,
    'source': 'IDC Report 2025',
    'confidence': 0.8,
    'date': '2025-01-15'
}
```

## The Complete Flow

```
User Query
    ↓
Entity Extraction (@Ramp, @Brex)
    ↓
Parallel Data Gathering (Tavily, GitHub, etc)
    ↓
Gap Filling (revenue, burn, runway inference)
    ↓
AI Impact Analysis (winner/traditional/cost center)
    ↓
Momentum Analysis (founding year, velocity)
    ↓
Market Analysis (TAM, capture %, adjacent)
    ↓
Scenario Modeling (base/bull/bear with AI adjustment)
    ↓
Cap Table Math (dilution, liquidation)
    ↓
Chart Generation (5 key visualizations)
    ↓
Claude Synthesis (narrative recommendation)
    ↓
Frontend Display (interactive dashboard)
```

## Output Structure
```json
{
  "recommendation": "Invest in @Ramp over @Brex because...",
  "comparisons": [
    {
      "company": "@Ramp",
      "fund_fit": 8.5,
      "ai_category": "traditional",
      "market_capture": "3% by 2030",
      "scenarios": {...},
      "charts": {...}
    }
  ],
  "visualizations": {
    "scenario_comparison": {...},
    "market_timeline": {...},
    "ownership_waterfall": {...}
  },
  "citations": {
    "market_size": ["IDC 2025", "Gartner 2024"],
    "comparables": ["Carta Q3 2025", "Bessemer 2024"]
  }
}
```