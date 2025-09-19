# Complete Deal Analysis Flow (Sep 2025)

## 1. DATA GATHERING (Frontend → Backend)
```
User Query: "Analyze @Ramp vs @Brex for Series C"
     ↓
Frontend: /api/agent/unified-brain
     ↓
Backend: UnifiedMCPOrchestrator
```

## 2. COMPANY DATA ENRICHMENT
```python
For each company:
├── Tavily Search (general, pricing, customers)
├── GitHub Analysis (momentum signals)
├── Funding History (from database)
├── Website Scraping (pricing tiers)
└── Customer Logos (enterprise signals)
```

## 3. INTELLIGENT GAP FILLING
```python
IntelligentGapFiller analyzes:
├── AI Impact Analysis
│   ├── AI Score (0-10)
│   ├── Agent Washing Detection
│   └── Category: winner/emerging/cost_center/traditional
│
├── Company Momentum
│   ├── Founded Year
│   ├── Funding Velocity
│   ├── Years to Unicorn
│   └── Momentum Score (0-10)
│
├── Market Multiples (from DB)
│   ├── Stage-based comparables
│   ├── Growth-adjusted multiples
│   └── Vintage adjustments (2021/2022 markdowns)
│
└── Inferred Metrics
    ├── Revenue (from pricing × customers)
    ├── Burn Rate (from funding cadence)
    ├── Runway (from last round)
    └── Growth Rate (from investor tier)
```

## 4. COMPREHENSIVE ANALYSIS
```python
ComprehensiveDealAnalyzer generates:
├── Market Analysis
│   ├── Current TAM: $40B (AI Infrastructure)
│   ├── 2030 TAM: $500B
│   ├── Market Growth: 85% CAGR
│   └── Citations: "IDC AI Forecast 2025"
│
├── Market Capture
│   ├── Year 1: 0.1% ($40M revenue potential)
│   ├── Year 5: 5% ($25B TAM = $1.25B revenue)
│   ├── Comparables: Stripe captured 2% in 14 years
│   └── Adjacent Markets: [MLOps, Data Tools, Training]
│
├── Scenarios (Base/Bull/Bear)
│   ├── Base: 5x return, 50% probability
│   ├── Bull: 10x return, 20% probability (AI winner)
│   └── Bear: 0.8x return, 30% probability (down round)
│
├── Cap Table Analysis
│   ├── Current: 10% ownership
│   ├── Exit (no participation): 6% diluted
│   ├── Exit (full pro-rata): 10% maintained
│   └── Liquidation Preference Impact
│
└── Fund Return Potential
    ├── Can Return Fund: Yes (if >$600M exit)
    ├── Probability: 40% (AI winner)
    └── Required Multiple: 30x on $5M investment
```

## 5. VISUALIZATIONS GENERATED
```python
charts = {
    'scenario_comparison': {
        type: 'grouped_bar',
        data: [base: 5x, bull: 10x, bear: 0.8x]
    },
    
    'ownership_dilution': {
        type: 'waterfall',
        data: [10% → 8% → 6% through rounds]
    },
    
    'market_capture': {
        type: 'line',
        data: [0.1% Y1 → 5% Y5 → 15% Y10]
    },
    
    'ai_momentum_radar': {
        type: 'radar',
        axes: [AI Score, Momentum, Growth, Moat, Market]
    },
    
    'liquidation_waterfall': {
        type: 'waterfall',
        scenarios: [M&A at 1x, 3x, 10x preference]
    }
}
```

## 6. FINAL PRESENTATION FORMAT

### Executive Summary
```markdown
**@Ramp** - AI Category: Traditional | Momentum: High | Founded: 2019
- Fund Fit Score: 8.5/10
- Market: $15B Expense Management → $40B by 2030
- Capture Potential: 3% by Year 10 = $1.2B revenue
- Adjacent Markets: Payments ($150B), Accounting ($40B)
```

### Investment Recommendation
```markdown
## Bull Case (20% probability)
- 10x return if captures 5% of expense management
- Natural expansion to payments (Square precedent)
- Strong momentum: 3 years to unicorn
- Citation: "Ramp grew 5x in 2024" - TechCrunch

## Base Case (50% probability)
- 5x return at $2B exit (current trajectory)
- Maintain 1% market share = $150M revenue
- Standard SaaS multiple of 10x revenue
- Citation: "Expense management growing 15% CAGR" - Gartner

## Bear Case (30% probability)
- 0.8x return (down round likely)
- 2021 vintage facing 35% markdown
- Competition from Brex, Divvy intensifying
- Citation: "2021 vintages trading at 65% of peak" - Carta
```

### Visual Dashboard
```
┌─────────────────────────────────────┐
│      Scenario Returns Chart         │
│  ████ Base: 5x                     │
│  ████████ Bull: 10x                │
│  ██ Bear: 0.8x                     │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│    Ownership Through Rounds         │
│  10% ──┐                           │
│        └─ 8% ──┐                   │
│                └─ 6% (exit)        │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│      Market Capture Timeline        │
│  2025: 0.1% = $15M                 │
│  2028: 1% = $200M                  │
│  2030: 3% = $1.2B                  │
│  Comparable: Brex at 2% in 6 years │
└─────────────────────────────────────┘
```

### Decision Matrix
```
                @Ramp       @Brex
Fund Fit:       8.5         7.8
AI Category:    Traditional Emerging
Momentum:       High        Very High
TAM:           $15B        $15B
Capture:       3%          5%
Down Risk:     Medium      Low
Agent Wash:    None        Medium
```

## 7. CITATIONS PROVIDED
Every data point is cited:
- Market sizes: "Gartner 2024", "IDC 2025"
- Growth rates: "Company disclosure", "PitchBook"
- Comparables: "Carta State of Private Markets"
- AI metrics: "Inferred from product analysis"
- Capture rates: "Bessemer State of Cloud 2024"

## FINAL OUTPUT TO CLAUDE
All this data is synthesized by Claude for final narrative:
- Which company to invest in and why
- Key differentiation factors
- Specific risks to monitor
- Follow-up diligence questions
- Investment committee presentation ready