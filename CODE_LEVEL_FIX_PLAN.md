# Code-Level Fix Plan: 61 → 100/100

**Current Score: 61/100**  
**Target: 100/100 (+39 points)**

---

## 🔴 **CRITICAL PATH: PDF Rendering (15 points)**

### Issue: Slides 9-15 empty/missing in PDF
**Root Cause:** Chart canvas elements exist but aren't painted before PDF generation

#### Fix 1: Add chart completion detection
**File:** `backend/app/services/deck_export_service.py`  
**Location:** Lines 3276-3294 (PDF generation wait logic)

**Current Code:**
```python
page.wait_for_timeout(3000)
canvas_count = page.evaluate("document.querySelectorAll('canvas').length")
page.wait_for_timeout(2000)
```

**Required Change:**
```python
# Wait for Chart.js AND for charts to actually render
page.wait_for_function("typeof Chart !== 'undefined'", timeout=15000)

# Check that charts are ACTUALLY drawn (not just initialized)
check_script = """
() => {
    const canvases = document.querySelectorAll('canvas');
    if (canvases.length === 0) return false;
    
    // Check if canvases have been drawn to
    for (let canvas of canvases) {
        const ctx = canvas.getContext('2d');
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const data = imageData.data;
        
        // Check if any pixels are non-transparent
        let hasContent = false;
        for (let i = 3; i < data.length; i += 4) {
            if (data[i] > 0) { // Alpha channel
                hasContent = true;
                break;
            }
        }
        if (!hasContent) return false;
    }
    return true;
}
"""

# Wait up to 10 seconds for charts to have actual content
try:
    page.wait_for_function(check_script, timeout=10000)
    logger.info("[PDF_GEN] All charts rendered with content")
except:
    logger.warning("[PDF_GEN] Timeout waiting for chart content, proceeding anyway")
    page.wait_for_timeout(3000)  # Fallback wait
```

#### Fix 2: Fix slide-specific HTML generation for missing slides
**File:** `backend/app/services/deck_export_service.py`  
**Location:** Lines 1571-1586 (HTML slide type routing)

**Issue:** Some slide types might not have HTML generators

**Check needed:**
```bash
# Grep for missing HTML generators
grep -n "slide_type.*cap_table_comparison\|exit_scenarios\|fund_return_impact\|followon" deck_export_service.py
```

**Required:** Ensure ALL these methods exist and return valid HTML:
- `_html_cap_table_comparison_slide()` - Line 1979 ✅ EXISTS
- `_html_exit_scenarios_comprehensive_slide()` - Line 2353 ✅ EXISTS  
- `_html_fund_impact_slide()` - Line 3825 ✅ EXISTS
- `_html_followon_strategy_slide()` - Line 3790 ✅ EXISTS

**Action:** Verify these methods return complete HTML with proper canvas IDs

---

## 🔴 **HIGH PRIORITY: Data Accuracy (12 points)**

### Issue 1: Sidekick revenue too low, wrong pricing
**File:** `backend/app/services/unified_mcp_orchestrator.py`  
**Location:** Company data enrichment (need to find exact line)

**Required Investigation:**
```python
# Search for where Sidekick data is fetched
grep -rn "Sidekick" backend/app/services/
grep -rn "revenue.*extraction\|inferred_revenue" backend/app/services/intelligent_gap_filler.py
```

**Fix Location:** `backend/app/services/intelligent_gap_filler.py`  
**Method:** `async def infer_from_funding_cadence()`

**Action:**
1. Add better revenue extraction from pitch deck
2. Use funding announcements to infer revenue (Series A companies typically 2-5M ARR)
3. Cross-validate with investor quality (tier 1 investors = higher revenue)

**Code Addition Needed:**
```python
def infer_revenue_from_funding_context(self, company_data: Dict) -> float:
    """Infer revenue from funding context - more accurate than pure calculation"""
    
    stage = company_data.get('stage', '')
    total_funding = company_data.get('total_funding', 0)
    last_round = company_data.get('last_funding_round', {})
    last_round_size = last_round.get('amount', 0)
    investors = company_data.get('investors', [])
    
    # Tier 1 investors indicate higher revenue at same stage
    tier_1_investors = ['a16z', 'sequoia', 'benchmark', 'accel', 'greylock', 
                        'kleiner', 'founders fund', 'index ventures']
    has_tier_1 = any(inv.lower() in tier_1_investors for inv in investors)
    
    # Base revenue by stage (conservative)
    revenue_by_stage = {
        'Pre-Seed': 0,
        'Seed': 500_000,      # $500K ARR
        'Series A': 3_000_000,  # $3M ARR
        'Series B': 15_000_000, # $15M ARR
        'Series C': 50_000_000  # $50M ARR
    }
    
    base_revenue = revenue_by_stage.get(stage, 1_000_000)
    
    # Adjust for tier 1 investors (they invest at higher revenue multiples)
    if has_tier_1:
        base_revenue *= 1.5
    
    # Adjust based on round size (larger rounds = more traction)
    if last_round_size > 0:
        if stage == 'Series A' and last_round_size > 15_000_000:
            base_revenue *= 1.3  # Large Series A = strong traction
        elif stage == 'Seed' and last_round_size > 5_000_000:
            base_revenue *= 1.5  # Large seed = exceptional traction
    
    return base_revenue
```

### Issue 2: Growth percentages showing 200% when should be ~100%
**File:** `backend/app/services/unified_mcp_orchestrator.py`  
**Location:** Lines 3182-3204 (Path to 100M slide)

**Current Issue:** Y-axis shows "1-60" instead of years, everyone has 200% YoY

**Fix:**
```python
# Replace hardcoded 1.2 (20% growth) with service-calculated growth
# Line ~3200: yoy_growth = 1.2  # REMOVE THIS

# Instead use:
from backend.app.services.intelligent_gap_filler import IntelligentGapFiller
gap_filler = IntelligentGapFiller()

# Get realistic growth rate
growth_data = gap_filler.calculate_required_growth_rates(company)
realistic_growth = growth_data.get('growth_scenarios', {}).get('realistic_years_to_100m_growth', 0.5)

# Use min of realistic growth OR calculated growth
yoy_growth = min(realistic_growth + 1, 2.0)  # Cap at 100% YoY (2.0 multiplier)
```

### Issue 3: Stage data wrong (Trig marked wrong stage)
**File:** `backend/app/services/unified_mcp_orchestrator.py`  
**Location:** Line 3025 (Company comparison slide)

**Issue:** Stage field ambiguous - is it what they raised or what they're raising?

**Fix:** Add stage detection logic
```python
def determine_accurate_stage(self, company_data: Dict) -> str:
    """Determine stage from funding history, not just latest round"""
    
    funding_rounds = company_data.get('funding_rounds', [])
    if not funding_rounds:
        return company_data.get('stage', 'Unknown')
    
    # Get MOST RECENT completed round
    completed_rounds = [r for r in funding_rounds if r.get('announced_date')]
    if not completed_rounds:
        return company_data.get('stage', 'Unknown')
    
    # Sort by date
    completed_rounds.sort(key=lambda x: x.get('announced_date', ''), reverse=True)
    latest = completed_rounds[0]
    
    round_type = latest.get('funding_type', '').lower()
    
    # Map funding type to stage
    stage_map = {
        'pre-seed': 'Pre-Seed',
        'seed': 'Seed',
        'series a': 'Series A',
        'series b': 'Series B',
        'series c': 'Series C'
    }
    
    for key, value in stage_map.items():
        if key in round_type:
            return value
    
    return company_data.get('stage', 'Unknown')
```

---

## 🟠 **MEDIUM PRIORITY: Chart Fixes (8 points)**

### Issue 1: Malformed bar chart (Slide 7)
**File:** `backend/app/services/unified_mcp_orchestrator.py`  
**Location:** Search for "grouped bar" or "comparison chart" generation

**Fix:** Replace grouped bar with stacked or side-by-side bars
```python
# Find the chart generation for scoring comparison
# Change chart type from 'grouped' to 'bar' with multiple datasets

chart_data = {
    "type": "bar",  # NOT "grouped-bar"
    "data": {
        "labels": company_names,
        "datasets": [
            {
                "label": "Moat Score",
                "data": moat_scores,
                "backgroundColor": "rgba(59, 130, 246, 0.8)"
            },
            {
                "label": "Momentum Score", 
                "data": momentum_scores,
                "backgroundColor": "rgba(16, 185, 129, 0.8)"
            },
            {
                "label": "Fund Fit Score",
                "data": fund_fit_scores,
                "backgroundColor": "rgba(139, 92, 246, 0.8)"
            }
        ]
    },
    "options": {
        "indexAxis": "y",  # Horizontal bars
        "scales": {
            "x": {"beginAtZero": true, "max": 100}
        }
    }
}
```

### Issue 2: Sankey diagram not rendering (Slide 11)
**File:** `backend/app/services/deck_export_service.py`  
**Location:** Lines 2550-2557 (Sankey placeholder code)

**Current:** Shows placeholder text  
**Fix:** Convert Sankey to simple ownership flow chart

```python
# In _generate_chart_scripts method
if chart_data.get('type') == 'sankey':
    # Convert Sankey data to waterfall chart
    sankey_nodes = chart_data.get('nodes', [])
    sankey_links = chart_data.get('links', [])
    
    # Create horizontal bar chart showing ownership changes
    ownership_data = self._convert_sankey_to_ownership_bars(sankey_nodes, sankey_links)
    
    simple_config = {
        "type": "bar",
        "data": ownership_data,
        "options": {
            "indexAxis": "y",
            "plugins": {
                "title": {"display": True, "text": "Ownership Evolution"}
            }
        }
    }
```

### Issue 3: Add waterfall chart (Slide 12)
**File:** `backend/app/services/unified_mcp_orchestrator.py`  
**Location:** Exit scenarios slide generation

**Add waterfall chart for exit proceeds:**
```python
def _create_waterfall_chart(self, company_name: str, exit_value: float, 
                           liquidation_pref: float, ownership_pct: float) -> Dict:
    """Create waterfall chart showing exit proceeds distribution"""
    
    # Waterfall: Exit Value → Liq Pref → Remaining → Our Share
    labels = ['Exit Value', 'Liq Pref', 'Remaining', 'Our Proceeds']
    
    remaining = exit_value - liquidation_pref
    our_proceeds = remaining * (ownership_pct / 100)
    
    data = [exit_value, -liquidation_pref, remaining, -remaining + our_proceeds]
    colors = ['#10b981', '#ef4444', '#3b82f6', '#8b5cf6']
    
    return {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{
                "data": data,
                "backgroundColor": colors
            }]
        },
        "options": {
            "plugins": {
                "title": {"display": True, "text": f"{company_name} Exit Waterfall"},
                "legend": {"display": False}
            }
        }
    }
```

---

## 🟠 **MEDIUM PRIORITY: Design Polish (7 points)**

### Issue 1: Ugly purple, inconsistent fonts, LLM-looking
**File:** `backend/app/services/deck_export_service.py`  
**Location:** Lines 1339-1523 (CSS styles)

**Changes needed:**

```css
/* REMOVE all purple/blue gradients */
/* Line ~1672: from-blue-50 to-purple-50 → CHANGE TO monochrome */

/* BEFORE: */
.bg-gradient-to-r from-blue-50 to-purple-50

/* AFTER: */
background: hsl(220, 10%, 97%);  /* Subtle warm gray */
border-left: 3px solid hsl(220, 22%, 20%);  /* Professional accent */
```

**Font standardization:**
```css
/* Line ~1376: Add font-feature-settings */
body {
    font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
    font-feature-settings: 'tnum' 1, 'ss01' 1;  /* Tabular numbers, stylistic set */
    letter-spacing: -0.011em;  /* Slightly tighter */
}

/* Headings - professional hierarchy */
h1, h2, h3 {
    font-weight: 600;  /* NOT 700 or 800 - too bold */
    letter-spacing: -0.02em;
}

.metric-value {
    font-variant-numeric: tabular-nums;  /* Aligned numbers */
    font-weight: 500;  /* NOT bold */
}
```

### Issue 2: Remove emojis (DONE in executive summary, check elsewhere)
**Files to check:**
```bash
grep -rn "📊\|📈\|💰\|🎯\|✅\|⚠️" backend/app/services/unified_mcp_orchestrator.py
```

**Replace all with:** Simple bullet points or remove entirely

---

## 🟡 **IMPORTANT: Add Analysis & Context (10 points)**

### Issue: "No actual analysis, just bad maths and shit charts"

**Current:** Slides show numbers with no context  
**Required:** Add WHY and SO WHAT to every metric

#### Fix 1: Add narrative context generator
**File:** `backend/app/services/unified_mcp_orchestrator.py`  
**Location:** NEW METHOD to add after line 2600

```python
def _generate_investment_narrative(self, company_data: Dict) -> Dict[str, str]:
    """Generate analyst-grade narrative context for metrics"""
    
    name = company_data.get('company', 'Company')
    revenue = self._safe_get_value(company_data.get('revenue', 0))
    valuation = self._safe_get_value(company_data.get('valuation', 0))
    stage = company_data.get('stage', 'Unknown')
    
    narratives = {}
    
    # Revenue multiple narrative
    if revenue > 0 and valuation > 0:
        multiple = valuation / revenue
        
        if multiple > 20:
            narratives['multiple'] = (
                f"{multiple:.1f}x revenue multiple reflects strong investor conviction in "
                f"future growth potential. This premium suggests {name} has demonstrated "
                f"exceptional unit economics, market traction, or defensible moats."
            )
        elif multiple < 3:
            narratives['multiple'] = (
                f"{multiple:.1f}x revenue multiple indicates either mature growth profile "
                f"or capital efficiency focus. For {stage} company, this suggests "
                f"path to profitability prioritized over hypergrowth."
            )
    
    # TAM narrative
    market_size = company_data.get('market_size', {})
    tam = market_size.get('tam', 0)
    if tam > 0 and revenue > 0:
        penetration = (revenue / tam) * 100
        
        if penetration < 0.1:
            narratives['market'] = (
                f"With <0.1% market penetration, {name} has significant whitespace "
                f"for expansion. Key question: can they scale GTM motion to capture "
                f"meaningful share before competition intensifies?"
            )
        elif penetration > 5:
            narratives['market'] = (
                f"At {penetration:.1f}% market share, {name} is approaching category "
                f"leadership. Growth from here requires either TAM expansion or "
                f"taking share from entrenched competitors."
            )
    
    # Funding efficiency narrative
    total_funding = company_data.get('total_funding', 0)
    if revenue > 0 and total_funding > 0:
        capital_efficiency = revenue / total_funding
        
        if capital_efficiency > 1:
            narratives['efficiency'] = (
                f"Revenue-to-funding ratio of {capital_efficiency:.2f}x demonstrates "
                f"exceptional capital efficiency. {name} is generating more revenue "
                f"than capital raised - rare for {stage} companies."
            )
        elif capital_efficiency < 0.3:
            narratives['efficiency'] = (
                f"Revenue-to-funding ratio of {capital_efficiency:.2f}x indicates "
                f"heavy investment in growth or product development. Returns will "
                f"depend on whether this burn translates to durable market position."
            )
    
    return narratives
```

#### Fix 2: Inject narratives into slides
**Location:** Each slide generation method

**Example for Slide 3 (Company Comparison):**
```python
# After metrics, add analysis section
narratives = self._generate_investment_narrative(company)

content["analysis"] = {
    "title": "Investment Perspective",
    "insights": [
        narratives.get('multiple', ''),
        narratives.get('market', ''),
        narratives.get('efficiency', '')
    ]
}
```

---

## 🟡 **IMPORTANT: TAM Calculation Fix (5 points)**

### Issue: "TAM calculations ridiculous, 5bn too low"

**File:** `backend/app/services/intelligent_gap_filler.py`  
**Method:** `calculate_market_opportunity()`

**Current problem:** Using outdated TAM sources or wrong calculation method

**Fix:**
```python
def calculate_market_opportunity_enhanced(self, company_data: Dict) -> Dict:
    """Enhanced TAM calculation with multiple methodologies"""
    
    sector = company_data.get('sector', '').lower()
    
    # Use LATEST market research (2024-2025 data)
    tam_benchmarks_2025 = {
        'fintech': 550_000_000_000,      # $550B (Stripe, Plaid, etc.)
        'hr tech': 35_000_000_000,       # $35B (Workday, Rippling, etc.)
        'sales tech': 80_000_000_000,    # $80B (Salesforce, etc.)
        'martech': 350_000_000_000,      # $350B (Segment, etc.)
        'devtools': 50_000_000_000,      # $50B (GitHub, etc.)
        'security': 200_000_000_000,     # $200B (Crowdstrike, etc.)
    }
    
    # Method 1: Top-down (category size)
    tam_topdown = tam_benchmarks_2025.get(sector, 50_000_000_000)
    
    # Method 2: Bottom-up (target customers × ACV)
    target_customers = company_data.get('target_customer_count', 100_000)
    avg_acv = company_data.get('acv', 50_000)  # $50K default for B2B SaaS
    tam_bottomup = target_customers * avg_acv
    
    # Method 3: Labor replacement value
    labor_tam = self._calculate_labor_replacement_tam(company_data)
    
    # Use MAXIMUM of all methods (most generous)
    tam = max(tam_topdown, tam_bottomup, labor_tam)
    
    return {
        'tam': tam,
        'methodology': 'Multi-method (top-down, bottom-up, labor replacement)',
        'breakdown': {
            'topdown': tam_topdown,
            'bottomup': tam_bottomup,
            'labor_replacement': labor_tam
        }
    }
```

---

## 🟡 **IMPORTANT: Add ESOP to Cap Tables (5 points)**

### Issue: "No ESOP in cap tables, needs forward-looking projections"

**File:** `backend/app/services/unified_mcp_orchestrator.py`  
**Location:** Cap table slide generation (search for "cap_table")

**Add ESOP analysis:**
```python
def _calculate_cap_table_with_esop(self, company_data: Dict) -> Dict:
    """Cap table WITH ESOP and future rounds projection"""
    
    from backend.app.services.advanced_cap_table import CapTableCalculator
    
    cap_table_calc = CapTableCalculator()
    
    # Current cap table
    current_valuation = company_data.get('valuation', 0)
    total_funding = company_data.get('total_funding', 0)
    
    # ESOP assumptions
    current_esop_pool = 0.10  # 10% is standard
    target_esop_pool = 0.15   # Will increase to 15% by Series B
    
    # Founder ownership (after dilution)
    founders_pct = max(0.40, 1 - (total_funding / current_valuation) - current_esop_pool)
    
    # Build future scenario
    future_rounds = []
    
    # Project Series A if they're seed
    stage = company_data.get('stage', '')
    if 'Seed' in stage or 'Pre-Seed' in stage:
        # Series A projection
        series_a_valuation = current_valuation * 3  # 3x step-up
        series_a_raise = series_a_valuation * 0.20  # Raise 20% dilution
        
        future_rounds.append({
            'round': 'Series A (projected)',
            'valuation': series_a_valuation,
            'dilution': 0.20,
            'esop_refresh': 0.05  # Add 5% more ESOP
        })
    
    # Calculate ownership at exit
    future_ownership = self._project_ownership_at_exit(
        current_ownership=founders_pct,
        future_rounds=future_rounds,
        esop_pool=target_esop_pool
    )
    
    return {
        'current': {
            'founders': founders_pct * 100,
            'investors': (1 - founders_pct - current_esop_pool) * 100,
            'esop_allocated': current_esop_pool * 0.30 * 100,  # 30% exercised
            'esop_unallocated': current_esop_pool * 0.70 * 100
        },
        'at_exit': future_ownership,
        'esop_analysis': {
            'current_pool': current_esop_pool * 100,
            'target_pool': target_esop_pool * 100,
            'exercised_assumption': 30,  # 30% exercise rate at exit
            'value_to_employees': current_valuation * target_esop_pool * 0.30
        }
    }
```

---

## 🟢 **POLISH: Recommendations & Scoring (4 points)**

### Issue: "Orphaned recommendations, unclear scoring"

**File:** `backend/app/services/unified_mcp_orchestrator.py`  
**Location:** Recommendation slide generation

**Add scoring methodology:**
```python
def _generate_recommendation_with_methodology(self, company_data: Dict, 
                                             fund_context: Dict) -> Dict:
    """Generate recommendation with TRANSPARENT scoring"""
    
    # Score components (out of 100 each)
    scores = {
        'moat': self._score_moat(company_data),
        'momentum': self._score_momentum(company_data),
        'market': self._score_market(company_data),
        'team': self._score_team(company_data),
        'fund_fit': self._score_fund_fit(company_data, fund_context)
    }
    
    # Weighted average
    weights = {'moat': 0.25, 'momentum': 0.30, 'market': 0.20, 
               'team': 0.15, 'fund_fit': 0.10}
    
    total_score = sum(scores[k] * weights[k] for k in scores)
    
    # Decision framework
    if total_score >= 75:
        recommendation = "STRONG INVEST"
        action = "Schedule partner meeting within 7 days"
    elif total_score >= 60:
        recommendation = "INVEST"
        action = "Proceed to full diligence"
    elif total_score >= 50:
        recommendation = "WATCH"
        action = "Monitor for 6 months, re-evaluate"
    else:
        recommendation = "PASS"
        action = "Focus on higher-conviction opportunities"
    
    return {
        'recommendation': recommendation,
        'action': action,
        'total_score': total_score,
        'component_scores': scores,
        'methodology': (
            f"Scored on 5 dimensions: Moat (25%), Momentum (30%), "
            f"Market (20%), Team (15%), Fund Fit (10%). "
            f"Threshold: >75 = Strong Invest, 60-75 = Invest, "
            f"50-60 = Watch, <50 = Pass"
        )
    }
```

---

## 🟢 **POLISH: Citations & Sources (2 points)**

### Issue: "Nonsense sources, empty in app"

**File:** `backend/app/services/unified_mcp_orchestrator.py`  
**Location:** Citations slide generation

**Add source validation:**
```python
def _validate_and_filter_citations(self, citations: List[Dict]) -> List[Dict]:
    """Remove nonsense citations and validate sources"""
    
    valid_citations = []
    
    # Whitelist of valid source domains
    valid_domains = [
        'crunchbase.com', 'pitchbook.com', 'cbinsights.com',
        'techcrunch.com', 'bloomberg.com', 'wsj.com',
        'company website', 'linkedin.com', 'sec.gov',
        'gartner.com', 'forrester.com', 'idc.com'
    ]
    
    for citation in citations:
        source = citation.get('source', '').lower()
        url = citation.get('url', '')
        
        # Skip if no source
        if not source:
            continue
        
        # Skip if obviously fake ("example.com", "placeholder", etc.)
        if any(fake in source for fake in ['example', 'placeholder', 'test', 'fake']):
            logger.warning(f"[CITATIONS] Skipping fake source: {source}")
            continue
        
        # Check if from valid domain
        is_valid = any(domain in source or domain in url for domain in valid_domains)
        
        if is_valid:
            valid_citations.append(citation)
    
    return valid_citations
```

---

## 📋 **IMPLEMENTATION ORDER**

### Phase 1: Critical Bugs (Days 1-2)
1. ✅ PDF black-on-black text (DONE)
2. ✅ Data validation - percentages (DONE)  
3. ⏳ PDF chart rendering detection
4. ⏳ Stage data accuracy

### Phase 2: Core Functionality (Days 3-4)
5. ⏳ Replace grouped bar charts
6. ⏳ Fix Sankey → ownership bars
7. ⏳ Add waterfall charts
8. ⏳ TAM calculation overhaul
9. ⏳ Revenue inference improvements

### Phase 3: Analysis & Context (Days 5-6)
10. ⏳ Add narrative generator
11. ⏳ Inject analysis into all slides
12. ⏳ Add scoring methodology to recommendations
13. ⏳ Add ESOP analysis to cap tables

### Phase 4: Design Polish (Day 7)
14. ⏳ Remove purple, standardize monochrome
15. ⏳ Font consistency
16. ⏳ Remove all emojis
17. ⏳ Professional spacing & hierarchy

### Phase 5: Final Quality (Day 8)
18. ⏳ Citation validation
19. ⏳ Remove contradictions (slide 15)
20. ⏳ Test full deck generation
21. ⏳ Verify PDF matches web exactly

---

## 🎯 **SUCCESS METRICS**

### Must Have (to reach 100/100):
- [ ] All 16 slides render in both web AND PDF
- [ ] No nonsense percentages (>100% ownership, >200% growth)
- [ ] All charts render correctly (no malformed bars, no missing Sankey)
- [ ] Every number has context ("so what?")
- [ ] Professional design (no purple, no emojis, no LLM look)
- [ ] ESOP in cap tables with forward projections
- [ ] Clear recommendation methodology
- [ ] Valid citations only

### Quality Checks:
- [ ] Revenue multiples: 2x - 50x (warn if outside)
- [ ] Ownership: 0.1% - 50% (recalculate if outside)
- [ ] Growth rates: 10% - 300% (validate if outside)
- [ ] TAM: >$10B for most tech categories
- [ ] Stage matches most recent funding round

---

## 📁 **FILES TO MODIFY**

1. **`backend/app/services/deck_export_service.py`** - PDF rendering, HTML generation
2. **`backend/app/services/unified_mcp_orchestrator.py`** - Slide content, data validation
3. **`backend/app/services/intelligent_gap_filler.py`** - Revenue/TAM inference
4. **`backend/app/services/advanced_cap_table.py`** - ESOP calculations
5. **`frontend/src/app/deck-agent/page.tsx`** - Web rendering consistency

---

**Ready to implement?** Start with Phase 1 (Critical Bugs) and work through systematically.
