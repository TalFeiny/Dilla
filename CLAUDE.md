# Dilla AI - Complete System Architecture (VERIFIED 2025-09-07)

## ACTUAL Data Flow Architecture (Corrected)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (Next.js)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  Pages/Components                 Frontend API Route                         │
│  ┌──────────────┐               ┌─────────────────────────────────────┐    │
│  │ Matrix Page  │──────────────→│ /api/agent/unified-brain/route.ts    │    │
│  │ Deck Agent   │               │                                      │    │
│  │ Fund Admin   │               │ Forwards to backend:                │    │
│  │ AgentRunner  │               │ ${BACKEND_URL}/api/agent/            │    │
│  └──────────────┘               │                unified-brain         │    │
│                                  └──────────────┬──────────────────────┘    │
└─────────────────────────────────────────────────┼────────────────────────────┘
                                                  │ HTTP POST
                                                  ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                            BACKEND (FastAPI)                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │ /api/agent/unified-brain endpoint (unified_brain.py:35)              │   │
│  │                                                                       │   │
│  │ orchestrator = get_unified_orchestrator()                           │   │
│  │ await orchestrator.process_request(prompt, output_format, context)  │   │
│  └────────────────────────────────┬─────────────────────────────────────┘   │
│                                    ↓                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │     UnifiedMCPOrchestrator.process_request() (Line 301-386)          │   │
│  │                                                                       │   │
│  │  1. Extract entities from prompt (Line 319)                         │   │
│  │  2. Analyze & build skill chain - ONE Claude call (Line 325)        │   │
│  │  3. Execute skill chain (parallel groups) (Line 339-365)            │   │
│  └────────────────────────────────┬─────────────────────────────────────┘   │
│                                    ↓                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │    _execute_skill_chain() → execute_skill() (Line 7320-7360)        │   │
│  │                                                                       │   │
│  │  skill_map = {                                                       │   │
│  │    'company-data-fetcher': _execute_company_fetch,  # Line 7324     │   │
│  │    'deal-comparer': _execute_deal_comparison,       # Line 7342     │   │
│  │    'valuation-engine': _execute_valuation,          # Line 7328     │   │
│  │  }                                                                   │   │
│  └──────────────────────────────┬───────────────────────────────────────┘   │
│                                  ↓                                           │
│         ┌────────────────────────┴─────────────────────────┐                │
│         ↓                                                  ↓                 │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  _execute_company_fetch() (Line 1770-2400) - MAIN DATA PIPELINE      │   │
│  │                                                                       │   │
│  │  async def fetch_single_company(company):  # Line 1785              │   │
│  │    ├─→ 4 PARALLEL Tavily searches (Lines 1790-1979)                │   │
│  │    │   ├─→ General: "{company} startup company"                     │   │
│  │    │   ├─→ Funding: "{company} raised seed series million"          │   │
│  │    │   ├─→ Website: Smart scoring algorithm (Lines 1871-1945)       │   │
│  │    │   └─→ Database: Supabase check                                 │   │
│  │    └─→ Returns raw search results                                   │   │
│  │                                                                       │   │
│  │  # Process ALL companies (Line 2242-2243)                           │   │
│  │  company_results = await asyncio.gather(*company_tasks)             │   │
│  │                                                                       │   │
│  │  For each company result: (Line 2252-2318)                          │   │
│  │    ├─→ StructuredDataExtractor (Line 2249-2282)                     │   │
│  │    │   └─→ Claude extracts from HTML → structured JSON              │   │
│  │    │                                                                 │   │
│  │    ├─→ _analyze_funding_data() (Line 2300)                         │   │
│  │    ├─→ _analyze_customer_data() (Line 2303)                        │   │
│  │    ├─→ _extract_company_metrics() (Line 2306)                      │   │
│  │    └─→ _estimate_valuation() (Line 2309)                           │   │
│  │                                                                       │   │
│  │  # Score companies (Line 2328-2400)                                 │   │
│  │  For each analyzed_company:                                          │   │
│  │    ├─→ Extract customer/metrics to top level (Lines 2329-2345)     │   │
│  │    ├─→ IntelligentGapFiller.infer_from_funding_cadence (Line 2351) │   │
│  │    ├─→ IntelligentGapFiller.infer_from_stage_benchmarks (Line 2361)│   │
│  │    ├─→ EXTRACT .value from InferenceResult (Lines 2380-2386)       │   │
│  │    └─→ score_fund_fit() → overall_score (Line 2389)                │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  _execute_deal_comparison() (Line 5318-5350)                        │   │
│  │                                                                       │   │
│  │  1. CALLS _execute_company_fetch() (Line 5330)                     │   │
│  │     └─→ Gets scored companies with all data                         │   │
│  │                                                                       │   │
│  │  2. _batch_synthesize_companies() (Line 5344)                      │   │
│  │     └─→ Single Claude call to compare all companies                 │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  _execute_valuation() (Line 2540-2878) - SEPARATE SKILL             │   │
│  │                                                                       │   │
│  │  Expects company_data with numeric fields already extracted:         │   │
│  │                                                                       │   │
│  │  1. CompanyScoringVisualizer.score_company() (Line 2607)            │   │
│  │  2. IntelligentGapFiller for missing data (Lines 2609-2644)         │   │
│  │  3. PrePostCapTable.calculate_full_cap_table_history (Line 2651)    │   │
│  │  4. AdvancedCapTable.calculate_liquidation_waterfall (Line 2665)    │   │
│  │  5. ValuationEngineService.calculate_valuation (Line 2694)          │   │
│  │  6. Generate scenarios & charts (Lines 2769-2838)                   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘

## CRITICAL DATA TRANSFORMATIONS

### 1. InferenceResult → Numeric (Lines 2380-2386)
```python
for field, inference in inferred.items():
    if hasattr(inference, 'value'):
        company_data[field] = inference.value  # Extract numeric value
        company_data[f"{field}_confidence"] = inference.confidence
```

### 2. Customer Dict → Numeric (Lines 2329-2334)
```python
if isinstance(company_data.get('customers'), dict):
    customers_dict = company_data['customers']
    company_data['customer_quality_score'] = self._ensure_numeric(
        customers_dict.get('customer_quality_score', 0))
```

### 3. Metrics Dict → Numeric (Lines 2335-2345)
```python
if isinstance(company_data.get('metrics'), dict):
    metrics_dict = company_data['metrics']
    company_data['arr'] = self._ensure_numeric(metrics_dict.get('arr', 0))
    company_data['revenue'] = self._ensure_numeric(metrics_dict.get('revenue', 0))
```

### 4. _ensure_numeric() Helper (Lines 6734-6778)
- Handles dict with 'value' key (from IntelligentGapFiller)
- Handles string formatting: $, commas, M/B/K suffixes
- Always returns float

## CRITICAL: Use Python Services for All Calculations
**Claude must NOT perform mathematical calculations directly. All valuations, cap tables, and financial projections MUST use the Python services below.**

### Advanced Python Valuation Services
1. **IntelligentGapFiller** (`backend/app/services/intelligent_gap_filler.py`)
   - `infer_from_funding_cadence()` - Project future rounds, burn rates, runway
   - `calculate_fund_fit_score()` - Score companies for investment fit
   - `calculate_ai_adjusted_valuation()` - AI impact on valuations
   - Handles dilution, next round timing, valuation projections

2. **PrePostCapTable** (`backend/app/services/pre_post_cap_table.py`)
   - `calculate_full_cap_table_history()` - Complete ownership evolution
   - Shows pre/post money ownership through all rounds
   - 75% options unexercised benchmark (Carta data)
   - Lead investor takes 60% of rounds

3. **AdvancedCapTable** (`backend/app/services/advanced_cap_table.py`)
   - Complex vesting schedules, liquidation preferences
   - Pro-rata rights, anti-dilution provisions
   - Waterfall analysis for exit scenarios
   - Share class management (Common, Preferred A-F, Options, SAFEs)

4. **ValuationEngineService** (`backend/app/services/valuation_engine_service.py`)
   - PWERM scenarios with probabilities
   - DCF with stage-specific discount rates
   - Comparables with DLOM adjustments
   - Industry multiples database

### Usage in Tools
- **deal_comparer**: Must use IntelligentGapFiller for each company
- **valuation_engine**: Must use ValuationEngineService.calculate_valuation()
- **execute_valuation**: Must use Python services, not agent iterations

## Project Overview
Dilla AI is a comprehensive VC platform with FastAPI backend and Next.js frontend, using Claude for AI-powered analysis.

## Deep Analysis Requirements
All agents MUST provide institutional-grade analysis:
1. **Financial**: CAC/LTV/burn/runway/valuation comps (5+ companies)
2. **Market**: TAM (bottom-up + top-down), competitive matrix, market timing
3. **Strategic**: 7 Powers moat analysis, exit scenarios (10+ buyers)
4. **Operational**: Team gaps, GTM metrics, unit economics
5. **Thesis**: 5+ bull/bear points, 10+ diligence questions

**Requirements**: Citations with dates, 2000+ word minimum, second-order insights

## Architecture Status

### Backend (FastAPI)
- **UnifiedMCPOrchestrator** (`backend/app/services/unified_mcp_orchestrator.py`) - Main orchestrator
- **MCPOrchestrator** (`backend/app/services/mcp_orchestrator.py`) - 50+ tools
- **Financial Tools**: DCF, NPV, IRR, PWERM calculations
- **Analytics**: Portfolio analysis, statistics, comparables
- **Data**: Database queries, embeddings, vector search
- **Visualization**: Charts, waterfalls, dashboards

### Data Fetching Flow (CRITICAL)
The `_execute_company_fetch` function now runs 4 parallel searches per company:
1. **General Search**: `{company} startup company` - Gets company overview
2. **Funding Search**: `{company} raised seed series million funding` - Gets funding history
3. **Website Search**: `{company} startup company` with smart scoring:
   - Scores URLs by domain match (100 pts for perfect match)
   - Extracts website from news articles if needed
   - Falls back to `{company} startup company website` if not found
4. **Database Search**: Checks Supabase for existing data

**Website Selection Algorithm**:
- Scoring system ranks potential websites
- Prioritizes direct company domains (company.com gets 100 points)
- Filters out dictionaries, wikis, social media
- Extracts website URLs from news article content if needed

### Frontend Integration
- **Main API**: `/api/agent/unified-brain/route.ts`
- **Backend Connector**: `/lib/mcp-backend-connector.ts`
- **Skills**: 9 specialized (company-sourcer, funding-aggregator, competitive-intelligence, deal-comparer, convertible-pricer, valuation-engine, deck-storytelling, chart-generator, cim-builder)

### Startup Commands
```bash
# Backend
cd backend && python3 -m uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev -p 3001
```

## IC Batch Processing
**Problem**: 50+ companies = 150 API calls
**Solution**: Parallel data fetching + IntelligentGapFiller scoring + single Claude synthesis

### Data Flow for Batch Processing
1. **Parallel Fetching**: All companies fetched in parallel (4 searches each)
2. **IntelligentGapFiller Processing**: Each company gets:
   - `infer_from_funding_cadence()` - Infers valuation, burn rate, runway
   - `infer_from_stage_benchmarks()` - Uses Carta/SVB stage data
   - `score_fund_fit()` - Scores against fund parameters
   - `analyze_ai_impact()` - AI category and valuation multiplier
   - `analyze_company_momentum()` - Growth trajectory scoring
3. **Single Claude Call**: Synthesizes all scored companies into recommendations

### Key Calculations
```python
# Burn Rate
monthly_burn = last_round_amount / assumed_runway_months
months_remaining = current_cash / monthly_burn

# Ownership (75% options unexercised - Carta benchmark)
diluted_ownership = initial_ownership * 0.75

# Exit Multiples
standard_saas = 5-7x revenue
strategic_ai = 14.66x  # OpenAI benchmark
```

## Fund Mathematics

### Portfolio Construction
- **Power Law**: 1-2 investments return fund (10-50x)
- **Loss Rate**: 40-60% acceptable with strong winners
- **Reserve Strategy**: 2-4x initial for winners

### Key Metrics
- **DPI**: Cash returned (what matters)
- **TVPI**: Paper value (can be gamed)
- **IRR**: Peaks year 7-8, then declines
- **J-Curve**: Negative years 1-3, positive 4+

### Exit Structures
- **IPO**: All convert to common, 180-day lockup, 15% dilution
- **M&A Cash**: Preferences stay, 20% tax, 10% escrow
- **M&A Stock**: 365-day lockup, acquirer stock risk
- **Acquihire**: Common gets zero

## Testing Guidelines

### Company Name Convention
**ALWAYS use @ prefix**: `@Ramp`, `@Deel`, `@Brex` (case-sensitive)

### Test Companies (NOT mega-corps like Stripe, Google, Microsoft)
- **Series A-B**: `@Ramp`, `@Mercury`, `@Brex`, `@Deel`, `@Lattice`
- **Series C-D**: `@Canva`, `@Figma`, `@Notion`, `@Airtable`, `@Miro`
- **Pre-seed/Seed**: `@Cursor`, `@Perplexity`, `@Clay`, `@Vanta`, `@Ashby`
- **Vertical SaaS**: `@Toast`, `@Procore`, `@Veeva`, `@Flexport`
- **Fintech**: `@Plaid`, `@Chime`, `@Affirm`, `@Marqeta`
- **AI/ML**: `@Anthropic`, `@Cohere`, `@Hugging Face`, `@Replicate`

### Example Queries
✅ "Compare @Deel and @Mercury for Series B investment"
✅ "Analyze @Cursor's unit economics and path to profitability"
✅ "Value @Clay using PWERM with $500M exit scenarios"
❌ "Compare Stripe and Square" (missing @, too well-known)
❌ "Analyze Microsoft acquisition" (mega-corp, not startup)

### TESTING NOTES
- DO NOT default to testing with @Ramp and @Brex
- Let the user choose their own test companies
- Always wait for user's specific test instructions

## System Verification - ALL CONNECTED ✅

### Key Integration Points Verified:
1. **Frontend → Backend**: `/api/agent/unified-brain` route working
2. **Skill Mapping**: All skills mapped in `execute_skill()` at Line 7320
3. **Data Pipeline**: `_execute_company_fetch` integrates all services
4. **Type Safety**: Data transformations prevent dict/numeric errors
5. **Service Integration**: All 6 valuation services properly called

---
Last Updated: 2025-09-07 | Status: FULLY OPERATIONAL - CORRECTED ARCHITECTURE