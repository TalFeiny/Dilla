# Dilla AI - System Architecture & Valuation Framework

## CRITICAL EXTRACTION RULES

**DO NOT ADD KEYWORDS TO "HELP" CATEGORIZATION**. When extracting company information:
- Describe EXACTLY what the company does, no buzzwords
- DO NOT add "AI-powered", "platform", "SaaS" unless that's literally what they do
- CoreWeave operates data centers → Say "operates data centers", NOT "AI cloud platform"
- nScale builds data centers → Say "builds data centers", NOT "infrastructure platform"

Example:
- WRONG: "AI-powered GPU cloud platform for machine learning" (adds keywords)
- RIGHT: "Operates 14 data centers with 45,000 GPUs for rent" (factual)

The system was broken because LLMs add keywords, then keyword matchers believe them. Trust the actual business description, not keywords.

## Important Model Update (November 2025)
**Current Date**: November 2025

**Available Models**:
- **Claude Sonnet 4.5** (`claude-sonnet-4-5`): Released September 29, 2025. Anthropic's flagship model with 30-hour autonomous operation capability, leading performance on SWE-bench, and improved computer use abilities. The system is configured to use Claude Sonnet 4.5 for all primary model calls.

- **GPT-5-Mini** (`gpt-5-mini`): Released in 2025. OpenAI's latest model available for use in the system. Configured as a cost-effective and fast alternative option in the model router.

Both models are confirmed as released and available for use as of November 2025.

## AI Valuation Framework (IPEV-Compliant)

### GPU Cost Per Transaction Analysis
Calculate actual GPU costs per usage, not arbitrary per-customer metrics:
- **Code generation** (Lovable, Cursor): $5-20 per full output
- **Search + synthesis** (Perplexity): $0.10-0.50 per query  
- **Chat exchanges**: $0.01-0.05 per interaction
- **Image/video generation**: $0.50-5.00 per asset

## CRITICAL: TAM & Market Sizing Requirements

### TAM Calculation Rules
**NEVER use generic multipliers or made-up numbers**. All TAM calculations MUST:

1. **Use Real Data Sources**:
   - BLS (Bureau of Labor Statistics) for workforce data
   - Industry reports (Gartner, IDC, Forrester) with dates
   - SEC filings for public company comparables
   - Trade association data with specific citations

2. **Labor TAM Requirements**:
   - MUST cite specific BLS occupation codes (e.g., SOC 43-4171 for receptionists)
   - Include exact workforce numbers and average salaries
   - NO generic `labor_tam = tam * 5` calculations
   - Example: "1.2M receptionists × $35K avg = $42B (BLS 2024)"

3. **Traditional TAM Sources**:
   - Market research firms with report dates
   - Bottom-up calculation from customer segments
   - Top-down from adjacent markets with clear logic
   - MUST include methodology explanation

4. **Data Quality Checks**:
   - TAM cannot be identical across different companies
   - Labor TAM must be specific to roles being replaced
   - SAM should be 10-30% of TAM (not 90%)
   - SOM should be 1-10% of SAM for early-stage

5. **Required Citations Format**:
   ```
   TAM: $42B healthcare reception labor (BLS SOC 43-4171: 1.2M workers @ $35K avg, 2024)
   SAM: $4.2B (10% of practices >50 employees)
   SOM: $420M (1% penetration Year 5)
   ```

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

## Current Status - December 2024

### ✅ Working
- Data fetching pipeline
- Business model categorization  
- Python valuation services
- Unified brain orchestration
- **NEW: Cap Table Comparison Slide (Slide #6)**
  - Side-by-side Sankey diagrams
  - Shows ownership flow through funding rounds
  - Compares two companies' cap tables
  - Visualizes our proposed investment

### ✅ Fixed (January 2025) - Deck Generation & TAM Calculation

#### Deck Generation Slides (unified_mcp_orchestrator.py Lines 1456-1603)
**Problem**: Missing key slides for investment analysis
**Fix**: Added Slide 5 (Path to $100M ARR) and Slide 6 (Business Analysis)
- Slide 5: Growth trajectory, time to $100M ARR, milestones
- Slide 6: What they do, what they sell, who they sell to
- Real cap table data integration using PrePostCapTable service
- Dynamic ownership calculation based on funding stage

#### TAM Labor Data NoneType Error (intelligent_gap_filler.py Lines 4789-4803)
**Problem**: Labor statistics returning None causing multiplication errors
**Root Cause**: When extracted data has `"labor_worker_count": null`, `.get()` returns None not 0
**Fix**: Wrap all labor data retrieval with `_ensure_numeric()`:
```python
# Lines 4789-4792
num_workers = self._ensure_numeric(labor_stats.get('number_of_workers'), 0)
avg_salary = self._ensure_numeric(labor_stats.get('avg_salary_per_role'), AVG_LABOR_COST)
total_addressable = self._ensure_numeric(labor_stats.get('total_addressable_labor_spend'), 0)
```
**Result**: Non-labor-replacing companies (like Mercury) properly fall back to minimal estimates

### ✅ Fixed (January 30, 2025) - Probability Cloud Implementation

#### Dynamic Probability-Weighted Breakpoint Visualization
**Problem**: Complex investment scenarios with probability distributions not visualized
**Solution**: Full implementation of probability cloud charts as described in `breaky.md`

**Backend Services (valuation_engine_service.py)**:
- `model_cap_table_evolution()`: Tracks dilution through funding rounds with investor quality adjustments
- `calculate_breakpoint_distributions()`: Computes probability distributions (p10-p90) for key breakpoints
- `generate_return_curves()`: Creates return multiples across exit values ($10M-$10B)

**Frontend Visualization (TableauLevelCharts.tsx)**:
- D3.js-based probability cloud with logarithmic scaling
- Scenario curves colored by exit type (IPO=green, Downside=red)
- Breakpoint probability bands showing p25-p75 and p10-p90 ranges
- Decision zones highlighting key investment thresholds
- Dynamic data from backend, no hardcoded values

**PDF Export (deck_export_service.py)**:
- Professional Chart.js multi-series line chart
- Up to 10 most probable scenarios with smooth curves
- Breakpoint annotations as vertical dashed lines
- Custom JavaScript function serialization for tooltips
- Complete data preservation with interpolation

**Key Features**:
- 100% dynamic calculation - no hardcoded probabilities
- Accounts for geography, investor quality, ESOP expansion
- IPO vs M&A exit mechanics properly modeled
- Real-time breakpoint calculation based on cap table evolution

### ✅ Fixed (January 29, 2025) - Deck Generation Data Issues

#### 1. InferenceResult Comparison Error (unified_mcp_orchestrator.py)
**Problem**: `'>' not supported between instances of 'InferenceResult' and 'int'`
**Fix**: Added `_safe_get_value()` helper method to extract values from InferenceResult objects
```python
def _safe_get_value(self, value: Any, default: Any = 0) -> Any:
    """Extract value from InferenceResult or return as-is"""
    if hasattr(value, 'value'):
        return value.value
    return value if value is not None else default
```

#### 2. Fund Fit Scoring Integration (Lines 753-797)
**Problem**: Fund fit calculations existed but weren't being used in deck generation
**Fix**: Added fund fit scoring after TAM calculation with actual fund context:
- 234M fund with 109M remaining to deploy
- Calculates actual ownership percentages
- Computes dilution through to exit
- Provides expected IRR and proceeds

#### 3. Business Data Extraction (Lines 1937-1981)
**Problem**: Using pattern matching instead of actual extracted data
**Fix**: Now uses real `product_description`, `target_market`, and `pricing_model` fields
- Falls back intelligently if data is generic
- Uses actual customer list when available
- Properly extracts pricing model from business description

#### 4. TAM Display with Real Data (Lines 2041-2099)
**Problem**: TAM using hardcoded multipliers instead of calculated market_size
**Fix**: Now uses `market_size` data from IntelligentGapFiller:
- Shows both traditional and labor TAM
- Includes real citations from search
- Displays labor replacement rate and total market
- Uses actual methodology description

#### 5. Investment Recommendations (Lines 4201-4265)
**Problem**: Generic recommendations without real ownership data
**Fix**: Uses actual fund fit calculations:
- Shows entry ownership → exit ownership after dilution
- Displays optimal check size from analysis
- Includes fund fit reasons and confidence scores
- Shows expected proceeds and IRR

### ✅ Fixed (December 2024)
- **Cap Table Visualization**: Now using Sankey diagrams for ownership flow
  - Position 6 in deck (before ownership analysis)
  - Side-by-side comparison for 2 companies
  - Proper data transformation from treemap to Sankey
  - Frontend device handler for `side_by_side_sankey`

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

### ⚠️ Remaining Issues
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

## Testing Companies
Use @ prefix for all companies: `@Ramp`, `@Deel`, `@Mercury`
- Series A-B: `@Mercury`, `@Brex`, `@Deel`
- AI/ML: `@Anthropic`, `@Perplexity`, `@Cursor`
- Vertical: `@Toast`, `@Veeva`, `@Procore`

## Data Quality Requirements (January 2025)

### Funding Data Validation
- Series C companies MUST have >$50M total funding
- Series B companies MUST have >$20M total funding  
- Series A companies MUST have >$5M total funding
- Flag and correct obvious errors (e.g., $119K for Series C)

### Revenue/Valuation Coherence
- Revenue cannot exceed valuation
- Valuation multiples must be stage-appropriate:
  - Seed: 50-100x ARR
  - Series A: 20-40x ARR
  - Series B: 10-20x ARR
  - Series C+: 5-15x ARR

### Business Model Specificity
- NEVER use generic "SaaS" - specify the actual service
- Include industry vertical in description
- Example: "Legal document automation for law firms" not "Legal SaaS"

### Missing Data Handling
- Always check for `inferred_` fields before using defaults
- Log confidence scores for inferred data
- Mark clearly in output when data is inferred vs actual

## Deck Structure (January 2025 - MAJOR UPDATE)

### ✅ Fixed Based on Feedback (January 28, 2025)
All deck generation issues have been addressed:

#### 1. Team Size Inference (intelligent_gap_filler.py Lines 827-870)
- **Problem**: Unrealistic employee counts (way too high)
- **Fix**: Reduced growth rate from 7% to 2.5% monthly, added hard caps
- **Caps**: Seed ≤35, Series A ≤120, Series B ≤350, Series C ≤800
- **Result**: Realistic headcount based on stage

#### 2. Executive Summary (unified_mcp_orchestrator.py Lines 1390-1436)
- **Problem**: Meaningless avg/combined valuations
- **Fix**: Added `_generate_executive_summary_bullets()` with:
  - Individual company metrics with revenue multiples
  - Labor replacement opportunities
  - Portfolio growth rates
  - Total deployment amounts
- **Result**: Actionable investment insights

#### 3. Company Overview (unified_mcp_orchestrator.py Lines 1488-1513)
- **Problem**: Valuation and revenue on separate slides
- **Fix**: Consolidated into single "Company Overview & Financials" slide with:
  - Revenue Multiple calculation
  - Capital Efficiency metrics
  - Properly formatted team sizes
- **Result**: All key metrics on one slide for easy comparison

#### 4. Path to $100M Chart (unified_mcp_orchestrator.py Lines 1565-1667)
- **Problem**: Y-axis values cut off, not in millions format
- **Fix**: 
  - Changed Y-axis to linear scale with "$M" format
  - Reduced timeline from 8 to 6 years
  - Added proper tick formatting callbacks
  - Better colors and point styling
- **Result**: Clear, readable growth projections

### Enhanced Investment Deck with Storytelling (16-18 slides):

#### Act I: The Opportunity (Slides 1-6)
1. **Title Slide** - Investment Analysis Report
2. **Executive Summary** - The investment thesis in 4 bullets
3. **Company Overview & Financials** - Side-by-side comparison with key metrics
4. **Founder & Team Analysis** - Leadership profiles, team composition, quality signals
   - Technical founder assessment
   - Previous exits and domain expertise
   - Team size appropriateness for stage
   - Hiring velocity and quality indicators

#### Act II: The Market (Slides 5-9)
5. **Path to $100M ARR** - Growth trajectory comparison
6. **Business Analysis** - What they do/sell/who they sell to
7. **Deep Market Dynamics** - Beyond TAM analysis
   - Market maturity and timing
   - Competitive landscape mapping
   - Growth drivers and tailwinds
   - Entry barriers and risks
   - Go-to-market strategy analysis
8. **Moat & Defensibility** - Long-term competitive advantages
   - 6-dimension moat scoring (0-10 scale)
   - Network effects, switching costs, data advantages
   - Economies of scale, brand, regulatory moats
   - Key differentiators and vulnerabilities
9. **TAM Pincer Analysis** - Traditional vs Labor TAM with citations

#### Act III: The Deal (Slides 10-14)
10. **Cap Table Evolution** - Individual company ownership waterfalls
11. **Cap Table Comparison** - Side-by-side Sankey diagrams
12. **Exit Scenarios (PWERM)** - Probability-weighted returns
13. **Investment Recommendations** - Fund fit for $260M fund
14. **Follow-on Strategy** - Ownership preservation through rounds

#### Act IV: The Impact (Slides 15-18)
15. **Fund Return Impact** - Portfolio construction analysis
16. **Risk Analysis** - Key risks and mitigations
17. **Decision Framework** - Why these companies, why now
18. **Citations** - All sources and references

### Key Improvements:
- **Data Quality**: Real calculations, no hardcoded values
- **Visualization**: Proper Sankey/waterfall charts with actual data
- **Formatting**: All monetary values in $M format
- **Team Sizes**: Realistic based on stage with hard caps
- **TAM Analysis**: Labor replacement properly calculated with BLS data

---
Last Updated: January 30, 2025 | Status: Probability cloud visualization complete - PDF export quality excellent with 100% dynamic calculations