# Dilla AI - System Architecture & Valuation Framework

## AI Valuation Framework (IPEV-Compliant)

### GPU Cost Per Transaction Analysis
Calculate actual GPU costs per usage, not arbitrary per-customer metrics:
- **Code generation** (Lovable, Cursor): $5-20 per full output
- **Search + synthesis** (Perplexity): $0.10-0.50 per query  
- **Chat exchanges**: $0.01-0.05 per interaction
- **Image/video generation**: $0.50-5.00 per asset

### Vertical vs Horizontal Classification
**Vertical SaaS** (Higher multiples: 15-25x)
- Deep industry focus (Veeva/pharma, Toast/restaurants)
- Defensible with domain expertise
- Limited TAM but high penetration potential
- Requires: TAM size, CAGR, current penetration %

**Horizontal SaaS** (Lower multiples: 8-12x)
- Cross-industry (Slack, Notion)
- Larger TAM but more competition
- Platform risk from big tech

### Labor Budget Arbitrage Theory
Enterprise labor spend = $2-3T annually. AI can capture 10-30%:

**Value Capture Split** (for $100K/year enterprise contract):
- $30-40K → OpenAI/Anthropic (GPU/API costs)
- $50-60K → AI SaaS company (workflow, integration, support)
- $10-20K → Gross margin (growth, R&D)

**Winners**: Own the workflow, high ACV, pass through GPU costs
- Harvey (legal): $500K ACV despite high GPU
- Glean (search): Replaces $2M Elasticsearch team

**Losers**: Thin wrappers without workflow ownership

### IPEV Valuation Multiple Formula
```
Multiple = Base SaaS Multiple × 
           (1 + Workflow_Ownership) × 
           (ACV / $100K) × 
           (1 - GPU_Passthrough_Ratio) ×
           (Vertical_Adjustment)
```

**Key Multipliers**:
- **Vertical + Low GPU**: 20-25x (best case)
- **Vertical + High GPU + Enterprise**: 10-15x (if ACV > $100K)
- **Horizontal + High GPU**: 2-5x (worst case)
- **High GPU + Consumer**: 2-3x (death)

## Critical Data Flow

### Main Pipeline: UnifiedMCPOrchestrator
1. **Frontend**: `/api/agent/unified-brain/route.ts`
2. **Backend**: `orchestrator.process_request()` (Line 301)
3. **Skills**: Maps to `_execute_company_fetch`, `_execute_valuation`, etc.

### Company Data Fetching (Lines 1770-2400)
- 4 parallel Tavily searches per company
- StructuredDataExtractor → Claude extraction
- IntelligentGapFiller → Inference & scoring
- Returns scored companies with valuations

### Business Model Detection Priority
1. AI-first (25x ARR)
2. Roll-up (4x ARR) - FIXED: now checked before services
3. Pure SaaS (10x ARR)
4. Services (2x revenue)

## Python Valuation Services (REQUIRED)

**Never calculate in Claude - always use these services:**

1. **IntelligentGapFiller** - Infers missing data, scores companies
2. **ValuationEngineService** - PWERM, DCF, Comparables
3. **PrePostCapTable** - Ownership evolution through rounds
4. **AdvancedCapTable** - Liquidation waterfalls, preferences

## Testing Guidelines

**Use @ prefix for all companies**: `@Ramp`, `@Deel`, `@Mercury`

**Test Companies**:
- Series A-B: `@Mercury`, `@Brex`, `@Deel`
- AI/ML: `@Anthropic`, `@Perplexity`, `@Cursor`
- Vertical: `@Toast`, `@Veeva`, `@Procore`

## CRITICAL REVENUE RULE
**NEVER have None type errors for revenue:**
1. First check for actual revenue: `company_data.get('revenue')` or `company_data.get('arr')`
2. If None/missing → use `company_data.get('inferred_revenue')` 
3. The inferred_revenue MUST ALWAYS exist - it's calculated for every company
4. NEVER use defaults like 1_000_000 - inferred_revenue should always be present
5. NEVER use `arr_median` directly - always use the inferred_revenue variable

## Current Status

### ✅ Working
- Data fetching pipeline
- Business model categorization  
- Python valuation services
- Unified brain orchestration

### ✅ Fixed (Sept 17th)
- **Revenue & Gross Margin Inference**: Fixed NoneType errors
  - Revenue now uses `arr_median` benchmarks with time-based growth since funding
  - Gross margin properly inferred based on business model (not overly negative)
  - All comparisons now handle None values safely
- **Time-Based Adjustments**: Revenue grows based on months since funding
  - Applies monthly compound growth from stage benchmark
  - Series A: 250% YoY → 11% monthly compound growth
- **Quality Adjustments**: Full stack of multipliers
  - Geography: SF/NYC get 1.1-1.15x revenue boost
  - Investors: Tier 1 VCs → 1.2x, Tier 2 → 1.1x
  - Customers: Enterprise logos → 1.3x
  - Team size, pricing model, etc all factor in

### ❌ BROKEN (Sept 18th) - Business Model & Vertical Extraction
- **Problem**: Companies showing as generic "SaaS" with "Unknown" sector
  - @Corti should be "Healthcare AI consultation analysis" not "SaaS"
  - @AdaptiveML should be "ML Infrastructure platform" not "SaaS"
  - DefenseTech companies missing their vertical entirely

- **Root Causes Identified**:
  1. Multiple conflicting extraction systems overwriting each other
  2. Generic prompts in `_extract_comprehensive_profile` returning "SaaS"
  3. Override logic replacing Claude's specific extractions with generic categories
  4. Fixed category lists instead of dynamic extraction

- **Attempted Fixes**:
  - ✅ Updated prompts to request specific descriptions
  - ✅ Removed override logic that was replacing good data
  - ❌ Still broken - extraction pipeline not working properly

### ⚠️ Other Remaining Issues
- **Article Date Extraction**: Need full dates from article URLs/metadata
  - Currently shows "2024-03" instead of exact date like "2024-03-15"
  - Required for time-based valuation adjustments
- **Currency Support**: Multi-currency extraction working but needs validation
  - £, €, $ symbols detected correctly
  - Gap filler handles normalization

### ✅ Fixed (Sept 16th)
- **Deck Agent**: No re-render issues found, components properly optimized
  - AgentChartGenerator useEffect dependencies correctly set (line 141)
  - Proper null checks and fallbacks in place
  - Build successful with no errors
- Output format handlers (deck/matrix/docs) need fixes
- Spreadsheet missing numeric data

## Startup Commands
```bash
# Backend
cd backend && python3 -m uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev -p 3001
```

## Testing Note
⚠️ **Business model extraction currently broken** - companies return as generic "SaaS"
Test with: `@Corti`, `@AdaptiveML`, `@Delian` to verify when fixed

---
Last Updated: 2025-09-18 | Focus: Fixing Business Model & Vertical Extraction