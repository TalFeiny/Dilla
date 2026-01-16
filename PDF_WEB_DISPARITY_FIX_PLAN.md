# PDF/Web Disparity Fix Plan - Code Level Implementation

## Problem Summary
- Slides 9-15 missing in PDF (cap tables, exit scenarios, DPI, follow-on, recommendations)
- Charts not rendering properly in PDF
- Style inconsistencies between web and PDF
- Hardcoded/nonsense data in multiple slides
- Poor chart types (grouped bar not supported, wrong chart for cap tables)
- Missing actual analysis - just basic math with no insights

## Phase 1: Fix PDF Chart Rendering (Critical)

### File: `backend/app/services/deck_export_service.py`

#### 1.1 Increase Chart Rendering Wait Time
**Location:** Lines 3096, 3021
```python
# CHANGE FROM:
page.wait_for_timeout(2000)

# CHANGE TO:
page.wait_for_timeout(8000)  # 8 seconds for complex charts
await page.evaluate('() => new Promise(resolve => requestAnimationFrame(resolve))')  # Wait for frame
```

#### 1.2 Add Chart Validation and Error Logging
**Location:** After line 1318
```python
# ADD NEW METHOD:
def _validate_slide_content(self, slide_data: Dict[str, Any], slide_idx: int) -> bool:
    """Validate slide has required content for rendering"""
    slide_type = slide_data.get("type", "unknown")
    content = slide_data.get("content", {})
    
    # Validate chart data if present
    if content.get("chart_data"):
        chart_data = content["chart_data"]
        if not chart_data.get("data"):
            logger.error(f"Slide {slide_idx} ({slide_type}): Missing chart data.data")
            return False
        if not chart_data["data"].get("labels"):
            logger.error(f"Slide {slide_idx} ({slide_type}): Missing chart data.data.labels")
            return False
        if not chart_data["data"].get("datasets"):
            logger.error(f"Slide {slide_idx} ({slide_type}): Missing chart data.data.datasets")
            return False
    
    # Validate multi-chart slides
    if slide_type == "exit_scenarios_comprehensive" and content.get("charts"):
        for idx, chart in enumerate(content["charts"]):
            if not chart.get("data") or not chart["data"].get("labels"):
                logger.error(f"Slide {slide_idx} chart {idx}: Invalid chart data")
                return False
    
    return True

# MODIFY _generate_html_deck at line 1320:
try:
    if self._validate_slide_content(slide_data, slide_idx):
        slide_html = self._generate_html_slide(slide_data, slide_idx)
        slides_html.append(slide_html)
    else:
        logger.warning(f"Skipping invalid slide {slide_idx}")
        # Add placeholder slide with error info
        slides_html.append(self._html_error_slide(slide_data, slide_idx))
except Exception as e:
```

#### 1.3 Add Error Placeholder Slides
**Location:** Add new method after line 1518
```python
def _html_error_slide(self, slide_data: Dict[str, Any], slide_idx: int) -> str:
    """Generate error placeholder slide"""
    slide_type = slide_data.get("type", "unknown")
    return f"""
<div class="slide bg-red-50 p-12 flex items-center justify-center">
    <div class="text-center">
        <h2 class="text-2xl font-bold text-red-900 mb-4">⚠️ Slide Rendering Error</h2>
        <p class="text-red-700">Slide {slide_idx + 1} (type: {slide_type}) failed to render</p>
        <p class="text-sm text-red-600 mt-2">Check backend logs for details</p>
    </div>
</div>
    """
```

#### 1.4 Fix Sankey Diagram Rendering
**Location:** Replace `_html_sankey_slide` at line 2227
```python
def _html_sankey_slide(self, content: Dict[str, Any], slide_idx: int) -> str:
    """Generate Sankey diagram slide HTML - convert to stacked bar chart"""
    chart_data = content.get('chart_data', {})
    
    # Convert Sankey to stacked bar chart showing ownership evolution
    converted_chart = self._convert_sankey_to_stacked_bar(chart_data)
    
    return f"""
<div class="slide bg-white p-12">
    <h2 class="text-3xl font-bold text-gray-900 mb-4">{content.get('title', 'Ownership Evolution')}</h2>
    <p class="text-sm text-gray-600 mb-4">{content.get('subtitle', '')}</p>
    <div class="chart-container" style="height: 450px;">
        <canvas id="chart-{slide_idx}"></canvas>
    </div>
</div>
    """

def _convert_sankey_to_stacked_bar(self, sankey_data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Sankey diagram data to stacked bar chart"""
    # Extract nodes and links from Sankey data
    nodes = sankey_data.get('data', {}).get('nodes', [])
    links = sankey_data.get('data', {}).get('links', [])
    
    # Group by rounds/stages
    rounds = ['Pre-Seed', 'Seed', 'Series A', 'Exit']
    stakeholders = {}
    
    for link in links:
        source_node = nodes[link['source']]['name'] if isinstance(link['source'], int) else link['source']
        target_node = nodes[link['target']]['name'] if isinstance(link['target'], int) else link['target']
        value = link['value']
        
        # Build stakeholder data
        if target_node not in stakeholders:
            stakeholders[target_node] = []
        stakeholders[target_node].append(value)
    
    # Create stacked bar chart config
    return {
        'type': 'bar',
        'data': {
            'labels': rounds,
            'datasets': [
                {
                    'label': stakeholder,
                    'data': values,
                    'stack': 'ownership'
                }
                for stakeholder, values in stakeholders.items()
            ]
        }
    }
```

#### 1.5 Fix Exit Scenarios Chart Rendering
**Location:** Modify `_html_exit_scenarios_comprehensive_slide` at line 2283
```python
def _html_exit_scenarios_comprehensive_slide(self, content: Dict[str, Any], slide_idx: int) -> str:
    """Generate comprehensive exit scenarios slide HTML with proper chart layout"""
    
    # Render main probability cloud chart
    main_chart_html = ""
    if content.get("chart_data"):
        main_chart_html = f"""
        <div class="mb-6">
            <div class="chart-container" style="height: 400px;">
                <canvas id="chart-{slide_idx}-main"></canvas>
            </div>
        </div>
        """
    
    # Render breakpoint analysis charts - SIDE BY SIDE, not crammed
    breakpoint_charts_html = ""
    if content.get("charts"):
        # Limit to 2 charts max, display side-by-side
        charts_to_show = content["charts"][:2]
        breakpoint_charts_html = '<div class="grid grid-cols-2 gap-6 mb-6">'
        for chart_idx, chart in enumerate(charts_to_show):
            chart_id = f"chart-{slide_idx}-{chart_idx}"
            breakpoint_charts_html += f"""
            <div class="bg-white border border-gray-200 rounded-lg p-4">
                <h4 class="text-sm font-semibold text-gray-700 mb-3">{chart.get('title', '')}</h4>
                <canvas id="{chart_id}" style="height: 250px;"></canvas>
            </div>
            """
        breakpoint_charts_html += '</div>'
    
    return f"""
<div class="slide bg-white p-8">
    <h2 class="text-2xl font-bold text-gray-900 mb-4">{content.get('title', 'Exit Scenarios')}</h2>
    <p class="text-sm text-gray-600 mb-4">{content.get('subtitle', '')}</p>
    {main_chart_html}
    {breakpoint_charts_html}
</div>
    """
```

## Phase 2: Fix Data Quality Issues

### File: `backend/app/services/deck_generation_service.py` (or wherever deck content is generated)

#### 2.1 Fix Revenue Multiples Slide (Slide 2)
**Problem:** Revenue multiples wrong, fund ownership 365% (impossible)
```python
# FIND: Revenue multiple calculation
# ADD: Validation and bounds checking

def calculate_revenue_multiple(valuation: float, revenue: float) -> float:
    """Calculate revenue multiple with validation"""
    if revenue <= 0:
        logger.warning(f"Invalid revenue: {revenue}, cannot calculate multiple")
        return None
    
    multiple = valuation / revenue
    
    # Sanity check - most SaaS multiples are 5-25x
    if multiple > 100:
        logger.warning(f"Suspiciously high revenue multiple: {multiple}x")
    elif multiple < 0.5:
        logger.warning(f"Suspiciously low revenue multiple: {multiple}x")
    
    return multiple

def calculate_ownership_percentage(investment: float, post_money: float, dilution_factor: float = 1.0) -> float:
    """Calculate ownership with dilution"""
    base_ownership = (investment / post_money) * 100
    diluted_ownership = base_ownership * dilution_factor
    
    # Ownership cannot exceed 100%
    if diluted_ownership > 100:
        logger.error(f"Invalid ownership calculation: {diluted_ownership}% - capping at 100%")
        return min(diluted_ownership, 100.0)
    
    return diluted_ownership
```

#### 2.2 Fix Company Stage Detection (Slide 3)
**Problem:** Trig marked wrong stage - should check what they've raised, not what they're raising
```python
# MODIFY: Stage detection logic

def infer_company_stage(company_data: Dict[str, Any]) -> str:
    """Infer company stage from funding history"""
    funding_rounds = company_data.get('funding_rounds', [])
    
    if not funding_rounds:
        return 'Pre-Seed'
    
    # Check ACTUAL rounds raised (not what they're ready for)
    latest_round = funding_rounds[-1]
    round_type = latest_round.get('round_type', '').lower()
    
    stage_mapping = {
        'pre-seed': 'Pre-Seed',
        'pre seed': 'Pre-Seed',
        'preseed': 'Pre-Seed',
        'seed': 'Seed',
        'series a': 'Series A',
        'series b': 'Series B',
        'series c': 'Series C',
    }
    
    detected_stage = stage_mapping.get(round_type, 'Unknown')
    logger.info(f"Company stage detected: {detected_stage} based on round: {round_type}")
    
    return detected_stage
```

#### 2.3 Fix Team Analysis (Slide 4)
**Problem:** Hardcoded "lean team for seed", no work history, fake technical co-founder info
```python
# REPLACE hardcoded team analysis with actual inference

async def analyze_founder_team(company_name: str, founders_data: List[Dict]) -> Dict[str, Any]:
    """Analyze founder team with real data"""
    
    team_analysis = {
        'founders': [],
        'team_size': None,
        'has_technical_cofounder': False,
        'key_experience': [],
        'concerns': []
    }
    
    for founder in founders_data:
        founder_info = {
            'name': founder.get('name'),
            'title': founder.get('title'),
            'background': []
        }
        
        # Extract work history from LinkedIn/sources
        work_history = founder.get('work_history', [])
        if work_history:
            # Get last 2-3 positions
            for position in work_history[:3]:
                founder_info['background'].append({
                    'company': position.get('company'),
                    'title': position.get('title'),
                    'duration': position.get('duration')
                })
        else:
            team_analysis['concerns'].append(f"No work history found for {founder.get('name')}")
        
        # Detect technical background
        technical_titles = ['cto', 'engineer', 'developer', 'architect', 'technical']
        title_lower = founder.get('title', '').lower()
        if any(tech in title_lower for tech in technical_titles):
            team_analysis['has_technical_cofounder'] = True
        
        team_analysis['founders'].append(founder_info)
    
    # Infer team size from employee count or LinkedIn
    team_analysis['team_size'] = await infer_team_size(company_name)
    
    # Don't make up data
    if not team_analysis['founders']:
        team_analysis['concerns'].append("Limited founder information available")
    
    return team_analysis
```

#### 2.4 Fix Growth Chart Y-Axis and Numbers (Slide 5)
**Problem:** Y-axis 1-60 nonsense, everyone has 200% YoY, not realistic
```python
# FIX: Growth chart generation

def generate_growth_chart(company_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate realistic growth projections"""
    
    current_revenue = company_data.get('current_revenue', 0)
    stage = company_data.get('stage', 'Seed')
    
    # Realistic YoY growth rates by stage
    growth_rates = {
        'Pre-Seed': (1.5, 3.0),  # 150-300% (wide range, early stage)
        'Seed': (1.3, 2.5),       # 130-250%
        'Series A': (1.2, 2.0),   # 120-200%
        'Series B': (1.15, 1.5),  # 115-150%
    }
    
    min_growth, max_growth = growth_rates.get(stage, (1.2, 2.0))
    
    # Use actual growth rate if available
    if company_data.get('historical_growth'):
        actual_rate = company_data['historical_growth']
        # Use actual but bound it to reasonable range
        yoy_growth = max(min_growth, min(actual_rate, max_growth))
    else:
        # Use middle of range
        yoy_growth = (min_growth + max_growth) / 2
    
    # Generate projections
    current_date = datetime.now()
    projections = []
    
    for i in range(4):  # 4 years forward
        year = current_date.year + i
        revenue = current_revenue * (yoy_growth ** i)
        projections.append({
            'year': year,  # USE ACTUAL YEAR
            'revenue': round(revenue, 0),
            'growth_rate': round((yoy_growth - 1) * 100, 1) if i > 0 else None
        })
    
    # Y-axis should be 0 to max revenue + 20% buffer
    max_revenue = projections[-1]['revenue']
    y_axis_max = round(max_revenue * 1.2, -3)  # Round to nearest thousand
    
    return {
        'type': 'line',
        'data': {
            'labels': [p['year'] for p in projections],  # ACTUAL YEARS
            'datasets': [{
                'label': f'{company_data.get("name")} Revenue',
                'data': [p['revenue'] for p in projections],
                'yoy_growth': f"{round((yoy_growth - 1) * 100, 1)}%"
            }]
        },
        'options': {
            'scales': {
                'y': {
                    'min': 0,
                    'max': y_axis_max,
                    'title': {'text': 'Revenue ($)'}
                },
                'x': {
                    'title': {'text': 'Year'}
                }
            }
        }
    }
```

#### 2.5 Fix TAM Analysis (Slide 8)
**Problem:** No market definition, made-up "RevenueTech", no sources, poor calculations
```python
# ADD: Proper TAM analysis with sources

async def analyze_tam(company_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze Total Addressable Market with sources"""
    
    industry = company_data.get('industry')
    description = company_data.get('description', '')
    
    # Use Tavily to research market size
    from app.services.tavily_service import tavily_service
    
    search_query = f"{industry} market size TAM 2024"
    search_results = await tavily_service.search(search_query, max_results=5)
    
    tam_analysis = {
        'market_definition': None,
        'tam_value': None,
        'sam_value': None,
        'som_value': None,
        'calculation_method': None,
        'sources': [],
        'assumptions': []
    }
    
    # Extract market data from search results
    for result in search_results:
        content = result.get('content', '')
        # Parse market size mentions
        # Look for patterns like "$X billion market" or "market of $X"
        import re
        market_matches = re.findall(r'\$([0-9.]+)\s*(billion|million|B|M)', content, re.IGNORECASE)
        
        if market_matches:
            tam_analysis['sources'].append({
                'title': result.get('title'),
                'url': result.get('url'),
                'snippet': content[:200]
            })
    
    # Define the market clearly
    tam_analysis['market_definition'] = f"Market for {industry} solutions targeting {company_data.get('target_customer', 'businesses')}"
    
    # Calculate TAM -> SAM -> SOM with clear methodology
    if tam_analysis['tam_value']:
        # SAM = TAM * addressable segment %
        tam_analysis['sam_value'] = tam_analysis['tam_value'] * 0.1  # 10% typically addressable
        # SOM = SAM * realistic capture rate
        tam_analysis['som_value'] = tam_analysis['sam_value'] * 0.05  # 5% market share is aggressive
        
        tam_analysis['calculation_method'] = "Top-down: Industry TAM → Addressable SAM (10%) → Serviceable SOM (5% capture)"
        tam_analysis['assumptions'] = [
            f"TAM based on total {industry} market size",
            "SAM limited to companies matching ICP (size, geography, tech stack)",
            "SOM assumes 5% market capture over 5 years (aggressive but achievable for category leaders)"
        ]
    else:
        tam_analysis['concerns'] = ["Unable to find reliable market size data"]
    
    return tam_analysis
```

#### 2.6 Fix Cap Table Charts (Slides 9-10)
**Problem:** Wrong chart type (bar instead of area/stacked), unclear Y-axis, missing investor data for Claimy
```python
# CHANGE: Cap table visualization to proper chart type

def generate_cap_table_chart(company_name: str, cap_table_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate proper cap table visualization - stacked area or waterfall"""
    
    rounds = cap_table_data.get('rounds', [])
    
    if not rounds:
        logger.warning(f"No cap table data for {company_name}")
        return None
    
    # Use STACKED AREA chart to show ownership evolution
    stakeholders = set()
    for round_data in rounds:
        stakeholders.update(round_data.get('stakeholders', {}).keys())
    
    datasets = []
    for stakeholder in stakeholders:
        data_points = []
        for round_data in rounds:
            ownership = round_data.get('stakeholders', {}).get(stakeholder, 0)
            data_points.append(ownership)
        
        datasets.append({
            'label': stakeholder,
            'data': data_points,
            'fill': True,
            'stack': 'ownership'
        })
    
    return {
        'type': 'line',  # With fill: true, becomes area
        'data': {
            'labels': [r.get('round_name', f'Round {i+1}') for i, r in enumerate(rounds)],
            'datasets': datasets
        },
        'options': {
            'scales': {
                'y': {
                    'min': 0,
                    'max': 100,
                    'title': {'text': 'Ownership %'},
                    'stacked': True
                },
                'x': {
                    'title': {'text': 'Funding Round'}
                }
            },
            'plugins': {
                'title': {
                    'display': True,
                    'text': f'{company_name} - Ownership Dilution Over Time'
                }
            }
        }
    }

# For getting investor data:
async def get_cap_table_with_investors(company_name: str) -> Dict[str, Any]:
    """Get cap table including investor names"""
    
    # Search for investor information
    from app.services.tavily_service import tavily_service
    
    search_query = f"{company_name} investors funding rounds crunchbase"
    results = await tavily_service.search(search_query, max_results=5)
    
    investors = []
    for result in results:
        # Parse investor names from content
        content = result.get('content', '')
        # Look for patterns like "led by X" or "investors include Y"
        # ... parsing logic ...
        
    return {
        'rounds': [],  # populated with round data
        'investors': investors,
        'sources': [r.get('url') for r in results]
    }
```

#### 2.7 Fix Exit Scenarios Math (Slide 12)
**Problem:** Hardcoded 10% ownership, wrong breakpoints (don't account for future rounds), not calculating properly
```python
# REPLACE: Hardcoded exit scenario logic

def calculate_exit_scenarios(
    company_data: Dict[str, Any],
    investment_amount: float,
    entry_ownership: float,  # ACTUAL ownership, not hardcoded
    entry_valuation: float
) -> Dict[str, Any]:
    """Calculate realistic exit scenarios with proper dilution"""
    
    stage = company_data.get('stage', 'Seed')
    
    # Estimate future dilution based on stage
    future_dilution = {
        'Pre-Seed': 0.60,  # Will raise Seed + A + B = ~40% dilution per round = 60% remaining
        'Seed': 0.70,      # Will raise A + B = 70% remaining
        'Series A': 0.85,  # Will raise B maybe = 85% remaining
        'Series B': 0.95,  # Last round likely
    }
    
    dilution_factor = future_dilution.get(stage, 0.70)
    exit_ownership = entry_ownership * dilution_factor
    
    logger.info(f"Exit ownership: {entry_ownership}% → {exit_ownership}% (dilution: {dilution_factor})")
    
    # Calculate breakpoints properly
    # 1. Liquidation preference breakpoint
    liquidation_pref = investment_amount * 1.0  # 1x pref typical
    liq_pref_breakpoint = liquidation_pref / (exit_ownership / 100)
    
    # 2. Conversion point (where % ownership equals liq pref)
    conversion_point = liq_pref_breakpoint
    
    # 3. Target multiple breakpoints
    target_moics = [3, 5, 10]
    exit_scenarios = []
    
    for moic in target_moics:
        target_proceeds = investment_amount * moic
        required_exit_value = target_proceeds / (exit_ownership / 100)
        
        # Account for liquidation preference
        if required_exit_value < conversion_point:
            # Below conversion - get liq pref only
            actual_proceeds = liquidation_pref
            actual_moic = actual_proceeds / investment_amount
        else:
            # Above conversion - use % ownership
            actual_proceeds = required_exit_value * (exit_ownership / 100)
            actual_moic = actual_proceeds / investment_amount
        
        exit_scenarios.append({
            'moic': moic,
            'exit_value': required_exit_value,
            'our_proceeds': actual_proceeds,
            'actual_moic': actual_moic,
            'exit_ownership': exit_ownership
        })
    
    return {
        'scenarios': exit_scenarios,
        'breakpoints': {
            'liquidation_preference': liquidation_pref,
            'conversion_point': conversion_point,
            'dilution_assumed': f"{(1-dilution_factor)*100:.0f}% future dilution"
        },
        'assumptions': [
            f"Entry ownership: {entry_ownership:.1f}%",
            f"Exit ownership: {exit_ownership:.1f}% (after {(1-dilution_factor)*100:.0f}% dilution from future rounds)",
            f"1x liquidation preference: ${liquidation_pref:,.0f}",
            f"Conversion at ${conversion_point:,.0f} exit value"
        ]
    }
```

#### 2.8 Fix DPI Calculation (Slide 13)
**Problem:** Uses old fund context, doesn't make sense
```python
# FIX: DPI calculation with proper fund context

def calculate_dpi_impact(
    fund_data: Dict[str, Any],
    investment: Dict[str, Any],
    exit_value: float
) -> Dict[str, Any]:
    """Calculate DPI impact with current fund data"""
    
    fund_size = fund_data.get('total_fund_size', 100_000_000)  # Get actual fund size
    total_invested = fund_data.get('total_invested', 0)
    total_realized = fund_data.get('total_realized', 0)
    
    # Current DPI
    current_dpi = total_realized / fund_size if fund_size > 0 else 0
    
    # Calculate proceeds from this exit
    investment_amount = investment.get('amount', 0)
    ownership = investment.get('current_ownership', 0)
    proceeds = exit_value * (ownership / 100)
    moic = proceeds / investment_amount if investment_amount > 0 else 0
    
    # New DPI after this exit
    new_realized = total_realized + proceeds
    new_dpi = new_realized / fund_size
    dpi_improvement = new_dpi - current_dpi
    
    # Contribution to fund target (typically 3x)
    fund_target_dpi = 3.0
    contribution_to_target = dpi_improvement / fund_target_dpi * 100
    
    return {
        'current_dpi': round(current_dpi, 2),
        'new_dpi': round(new_dpi, 2),
        'dpi_improvement': round(dpi_improvement, 2),
        'proceeds': proceeds,
        'moic': round(moic, 1),
        'contribution_to_fund_target': f"{contribution_to_target:.1f}%",
        'fund_context': {
            'fund_size': fund_size,
            'total_invested': total_invested,
            'total_realized': total_realized,
            'target_dpi': fund_target_dpi
        }
    }
```

#### 2.9 Fix Follow-On Analysis (Slide 14)
**Problem:** Hardcoded nonsense
```python
# REPLACE: Hardcoded follow-on with real analysis

def analyze_followon_strategy(
    company_data: Dict[str, Any],
    initial_investment: Dict[str, Any],
    fund_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Analyze follow-on investment strategy"""
    
    stage = company_data.get('stage', 'Seed')
    performance = company_data.get('performance_metrics', {})
    
    # Determine if follow-on makes sense
    followon_triggers = []
    followon_concerns = []
    
    # Check performance metrics
    revenue_growth = performance.get('revenue_growth_rate', 0)
    if revenue_growth > 1.5:  # 150%+ growth
        followon_triggers.append(f"Strong growth: {revenue_growth:.0%} YoY")
    elif revenue_growth < 0.5:  # <50% growth
        followon_concerns.append(f"Weak growth: {revenue_growth:.0%} YoY")
    
    # Check if we have enough reserves
    fund_reserves = fund_data.get('reserves', 0)
    initial_check = initial_investment.get('amount', 0)
    typical_followon = initial_check * 2  # 2x initial check
    
    if fund_reserves < typical_followon:
        followon_concerns.append(f"Insufficient reserves: ${fund_reserves:,.0f} available vs ${typical_followon:,.0f} needed")
    
    # Check ownership
    current_ownership = initial_investment.get('current_ownership', 0)
    if current_ownership < 5:
        followon_triggers.append(f"Need to maintain ownership (currently {current_ownership:.1f}%)")
    
    # Recommendation
    if len(followon_triggers) > len(followon_concerns) and fund_reserves >= typical_followon:
        recommendation = "FOLLOW-ON"
        rationale = "Strong performance and sufficient reserves justify follow-on investment"
        suggested_amount = typical_followon
    else:
        recommendation = "MONITOR"
        rationale = "Concerns outweigh triggers - monitor performance before follow-on decision"
        suggested_amount = 0
    
    return {
        'recommendation': recommendation,
        'rationale': rationale,
        'suggested_amount': suggested_amount,
        'triggers': followon_triggers,
        'concerns': followon_concerns,
        'analysis': {
            'current_ownership': current_ownership,
            'post_followon_ownership': None,  # Calculate if following on
            'fund_reserves_available': fund_reserves
        }
    }
```

#### 2.10 Fix Recommendations (Slide 15)
**Problem:** Hardcoded pass/invest contradiction, obsessed with 10%, red "PASS" but says "schedule meeting"
```python
# FIX: Investment recommendation logic

def generate_investment_recommendation(
    company_data: Dict[str, Any],
    analysis_results: Dict[str, Any],
    fund_fit: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate consistent investment recommendation"""
    
    # Score different aspects (0-10 scale)
    scores = {
        'team': score_team(company_data.get('team_analysis', {})),
        'market': score_market(analysis_results.get('tam_analysis', {})),
        'traction': score_traction(company_data.get('performance_metrics', {})),
        'financials': score_financials(company_data.get('financials', {})),
        'fund_fit': score_fund_fit(fund_fit)
    }
    
    # Calculate weighted average
    weights = {'team': 0.25, 'market': 0.20, 'traction': 0.25, 'financials': 0.15, 'fund_fit': 0.15}
    overall_score = sum(scores[k] * weights[k] for k in scores.keys())
    
    # Determine recommendation based on score
    if overall_score >= 7.5:
        decision = "STRONG INVEST"
        color = "green"
        action = "Schedule partner meeting immediately"
    elif overall_score >= 6.0:
        decision = "INVEST"
        color = "green"
        action = "Schedule diligence call"
    elif overall_score >= 4.5:
        decision = "MAYBE"
        color = "yellow"
        action = "Request more information before deciding"
    else:
        decision = "PASS"
        color = "red"
        action = "Politely decline and stay in touch"
    
    # Calculate target ownership (not hardcoded)
    investment_size = fund_fit.get('typical_check_size', 1_000_000)
    valuation = company_data.get('valuation', 10_000_000)
    target_ownership = (investment_size / valuation) * 100
    
    # Adjust for stage
    stage = company_data.get('stage', 'Seed')
    min_ownership_by_stage = {
        'Pre-Seed': 5.0,
        'Seed': 7.0,
        'Series A': 10.0,
        'Series B': 12.0
    }
    min_ownership = min_ownership_by_stage.get(stage, 10.0)
    
    if target_ownership < min_ownership:
        scores['fund_fit'] *= 0.5  # Penalize
        if decision in ["STRONG INVEST", "INVEST"]:
            decision = "MAYBE"
            action = f"Negotiate for {min_ownership}% minimum ownership"
    
    return {
        'decision': decision,
        'action': action,  # CONSISTENT with decision
        'color': color,
        'overall_score': round(overall_score, 1),
        'dimension_scores': scores,
        'investment_terms': {
            'proposed_investment': investment_size,
            'target_ownership': round(target_ownership, 1),
            'minimum_ownership': min_ownership,
            'ownership_acceptable': target_ownership >= min_ownership
        },
        'key_strengths': extract_strengths(scores),
        'key_concerns': extract_concerns(scores)
    }

def score_team(team_analysis: Dict) -> float:
    """Score team quality (0-10)"""
    score = 5.0  # Neutral start
    
    if team_analysis.get('has_technical_cofounder'):
        score += 2.0
    
    founders = team_analysis.get('founders', [])
    for founder in founders:
        if len(founder.get('background', [])) > 0:
            score += 0.5  # Has work history
    
    if team_analysis.get('concerns'):
        score -= len(team_analysis['concerns']) * 0.5
    
    return max(0, min(10, score))

# Similar scoring functions for market, traction, financials, fund_fit...
```

## Phase 3: Unify Styling

### File: `backend/app/services/deck_export_service.py`

#### 3.1 Use Same Tailwind Config as Web
**Location:** Line 1334
```typescript
// CHANGE FROM: CDN
<script src="https://cdn.tailwindcss.com"></script>

// CHANGE TO: Inline the actual config from frontend/tailwind.config.js
<script src="https://cdn.tailwindcss.com"></script>
<script>
    tailwind.config = {
        theme: {
            extend: {
                fontFamily: {
                    sans: ['Inter', 'system-ui', 'sans-serif'],
                    serif: ['Playfair Display', 'Georgia', 'serif'],
                    mono: ['IBM Plex Mono', 'monospace']
                },
                colors: {
                    // Match frontend colors exactly
                    primary: {
                        50: '#f0f9ff',
                        // ... rest of colors from frontend
                    }
                }
            }
        }
    }
</script>
```

#### 3.2 Remove "AI-looking" Font Issues
**Location:** Update typography in HTML templates
```python
# CHANGE: Font styling to be more professional
# Remove: Playfair Display (too decorative)
# Use: Inter for everything, IBM Plex Sans for metrics

# In _html_title_slide and all slides:
# class="font-serif" → class="font-sans"
# Make it look like a professional pitch deck, not an AI creation
```

## Phase 4: Chart Type Fixes

### Files: Backend deck generation + frontend chart components

#### 4.1 Replace Grouped Bar Charts
**Problem:** "Grouped bar not supported" (Slide 7)
```python
# Find where grouped bar charts are created
# Replace with side-by-side standard bar charts

def convert_grouped_to_sidebyside(chart_config: Dict) -> Dict:
    """Convert grouped bar to two separate charts"""
    datasets = chart_config.get('data', {}).get('datasets', [])
    
    # Split into two charts
    chart1 = {
        'type': 'bar',
        'data': {
            'labels': chart_config['data']['labels'],
            'datasets': [datasets[0]] if len(datasets) > 0 else []
        }
    }
    
    chart2 = {
        'type': 'bar',
        'data': {
            'labels': chart_config['data']['labels'],
            'datasets': [datasets[1]] if len(datasets) > 1 else []
        }
    }
    
    return {'left': chart1, 'right': chart2}
```

## Phase 5: Add Logging and Debugging

### File: `backend/app/services/deck_export_service.py`

#### 5.1 Add Detailed PDF Generation Logging
```python
# At line 3084 in export_to_pdf:
logger.info(f"[PDF_EXPORT] Starting PDF generation")
logger.info(f"[PDF_EXPORT] Deck has {len(slides)} slides")

html = self._generate_html_deck(deck_data)

# Log HTML stats
logger.info(f"[PDF_EXPORT] Generated HTML: {len(html)} bytes")
logger.info(f"[PDF_EXPORT] Charts to render: {html.count('canvas id=\"chart-')}")

# Save debugging HTML
debug_path = f"/tmp/deck_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
with open(debug_path, "w") as f:
    f.write(html)
logger.info(f"[PDF_EXPORT] Debug HTML saved to: {debug_path}")

# After PDF generation:
logger.info(f"[PDF_EXPORT] PDF generated: {len(pdf_bytes)} bytes")
```

#### 5.2 Add Chart Rendering Success Tracking
```python
# In _generate_chart_scripts:
# Add console logging in the generated JavaScript

scripts.append("""
    console.log('Chart rendering started');
    let chartsRendered = 0;
    let chartsFailed = 0;
""")

# For each chart:
scripts.append(f"""
    try {{
        var ctx{slide_idx} = document.getElementById('chart-{slide_idx}');
        if (ctx{slide_idx}) {{
            new Chart(ctx{slide_idx}.getContext('2d'), {self._serialize_chart_config(chart_config)});
            chartsRendered++;
            console.log('Chart {slide_idx} rendered successfully');
        }} else {{
            chartsFailed++;
            console.error('Chart {slide_idx} canvas not found');
        }}
    }} catch(e) {{
        chartsFailed++;
        console.error('Chart {slide_idx} failed:', e);
    }}
""")

scripts.append("""
    console.log(`Charts rendered: ${chartsRendered}, failed: ${chartsFailed}`);
""")
```

## Phase 6: Add Analyst-Grade Analysis

### File: `backend/app/services/company_analysis_service.py` (new)

```python
"""
Company Analysis Service - Analyst-grade insights
"""

class CompanyAnalysisService:
    """Generate deep insights, not just basic math"""
    
    async def analyze_competitive_positioning(self, company_data: Dict, competitors: List[Dict]) -> Dict:
        """Analyze how company stacks up vs competitors"""
        # Compare on multiple dimensions
        # - Technology differentiation
        # - Go-to-market efficiency
        # - Capital efficiency
        # - Market position
        
    async def analyze_unit_economics(self, company_data: Dict) -> Dict:
        """Deep dive into unit economics"""
        # Calculate and interpret:
        # - CAC
        # - LTV
        # - LTV/CAC ratio
        # - Payback period
        # - Magic number
        
    async def analyze_market_dynamics(self, industry: str) -> Dict:
        """Analyze market forces and dynamics"""
        # - Market growth rate
        # - Competitive intensity
        # - Regulatory risks
        # - Technology trends
        
    async def identify_red_flags(self, company_data: Dict) -> List[str]:
        """Identify potential deal-breakers"""
        # - Founder conflicts
        # - Legal issues
        # - Competitive threats
        # - Execution risks
        
    async def generate_investment_thesis(self, all_analysis: Dict) -> str:
        """Generate coherent investment thesis"""
        # Synthesize all analysis into narrative
        # Why this company, why now, why us
```

## Implementation Order

1. **Phase 1 (Critical)** - Fix PDF rendering (1-2 days)
   - Increases wait time
   - Adds validation
   - Fixes Sankey/chart issues
   
2. **Phase 2 (High Priority)** - Fix data quality (3-4 days)
   - Fix all hardcoded values
   - Add proper calculations
   - Validate data bounds
   
3. **Phase 3 (Medium)** - Unify styling (1 day)
   - Match web appearance
   - Remove AI-looking fonts
   
4. **Phase 4 (Medium)** - Fix chart types (1 day)
   - Replace unsupported charts
   - Use proper visualizations
   
5. **Phase 5 (Low)** - Add logging (0.5 days)
   - Debug issues
   - Track rendering
   
6. **Phase 6 (Enhancement)** - Analyst-grade analysis (5-7 days)
   - Deep insights
   - Real value-add

## Testing Checklist

After implementation:
- [ ] All 16 slides render in PDF
- [ ] All charts display correctly in PDF
- [ ] No hardcoded values (10%, 200% growth, etc.)
- [ ] Ownership percentages are realistic (<100%)
- [ ] Stage detection works correctly
- [ ] Team analysis uses real data
- [ ] Growth charts have proper axes with real years
- [ ] TAM analysis has sources
- [ ] Cap tables use proper chart types
- [ ] Exit scenarios use actual ownership and dilution
- [ ] DPI uses current fund data
- [ ] Follow-on recommendations are logical
- [ ] Investment recommendations are consistent
- [ ] Styling matches between web and PDF
- [ ] No "AI-looking" elements
- [ ] All citations are relevant

## Success Metrics

- PDF and web show same slides (16/16)
- All charts render in both (100% render rate)
- Data validation passes (0 impossible values)
- User feedback: "looks professional"
