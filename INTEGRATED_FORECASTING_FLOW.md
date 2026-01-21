# Integrated Exit Scenario Forecasting Flow

## Overview
All forecasting methods are now connected through shared assumptions from `intelligent_gap_filler`, ensuring revenue projections, cap table evolution, and exit values are all aligned.

## End-to-End Flow

### 1. **Data Enrichment Phase** (Before Valuation)
```
Company Data (raw)
    ↓
IntelligentGapFiller.infer_from_stage_benchmarks()
    ↓
Enriched company_data with:
  - inferred_growth_rate
  - inferred_gross_margin
  - inferred_burn_rate
  - quality_score (from investor tier, team size, market)
```

### 2. **Shared Assumptions Extraction** (ValuationEngineService)
```
company_data (with inferred values)
    ↓
_get_shared_assumptions(company_data)
    ↓
Calls intelligent_gap_filler methods:
  - gap_filler._calculate_company_quality_score() → quality_score
  - gap_filler.calculate_adjusted_gross_margin() → exit_multiple
  - Extracts: inferred_growth_rate, inferred_gross_margin, inferred_burn_rate
    ↓
Returns shared_assumptions dict:
  {
    'growth_rate': 1.5,        # From inferred_growth_rate
    'gross_margin': 0.75,      # From inferred_gross_margin
    'burn_rate': 2_000_000,     # From inferred_burn_rate
    'quality_score': 1.2,      # From gap_filler calculation
    'exit_multiple': 8.5,      # From gap_filler margin analysis
    'source': 'inferred'
  }
```

### 3. **Integrated Scenario Generation** (_generate_exit_scenarios)

For each exit scenario (e.g., "Strategic Premium Acquisition"):

#### Step 3a: Cap Table Evolution
```
scenario.funding_path = "seed→A→B→C"
    ↓
model_cap_table_evolution(scenario, company_data, our_investment)
    ↓
For each round in funding_path:
  - Uses PrePostCapTable service for base dilution
  - Uses shared_assumptions['quality_score'] for step-up multiples
  - Tracks: our_ownership, liquidation_pref, breakpoints
    ↓
Updates scenario:
  - scenario.cap_table_evolution = [...]
  - scenario.final_ownership = 0.08  # After all dilution
  - scenario.final_liq_pref = 45_000_000
```

#### Step 3b: Revenue Projection
```
base_revenue = company_data.get('inferred_revenue', 5_000_000)
shared_assumptions['growth_rate'] = 1.5  # 150% YoY
shared_assumptions['quality_score'] = 1.2
scenario.time_to_exit = 5.0 years
    ↓
_project_revenue_with_decay(
    base_revenue=5_000_000,
    initial_growth=1.5,  # From shared_assumptions
    years=5,
    quality_score=1.2,  # From shared_assumptions (slower decay)
    return_projections=True
)
    ↓
Returns year-by-year projections:
  [
    {year: 1, revenue: 12_500_000, growth_rate: 1.5},
    {year: 2, revenue: 28_125_000, growth_rate: 1.26},  # Decayed
    {year: 3, revenue: 59_062_500, growth_rate: 1.06},  # More decay
    {year: 4, revenue: 121_875_000, growth_rate: 0.89},
    {year: 5, revenue: 230_625_000, growth_rate: 0.75}  # Final
  ]
    ↓
Updates scenario:
  - scenario.revenue_projections = [...]
  - scenario.final_revenue = 230_625_000
```

#### Step 3c: Exit Value Calculation (Aligned with Revenue)
```
scenario.final_revenue = 230_625_000
shared_assumptions['exit_multiple'] = 8.5
    ↓
If acquihire:
  team_size = 50
  team_quality_multiplier = 1.2 * 200_000 = 240_000
  scenario.exit_value = 50 * 240_000 = 12_000_000
Else:
  scenario.exit_value = 230_625_000 * 8.5 = 1_960_312_500
    ↓
✅ Exit value is ALIGNED with revenue at exit time
```

#### Step 3d: Returns Calculation
```
scenario.exit_value = 1_960_312_500
scenario.final_ownership = 0.08  # From cap table evolution
our_investment = 10_000_000
    ↓
our_proceeds = 1_960_312_500 * 0.08 = 156_825_000
scenario.moic = 156_825_000 / 10_000_000 = 15.68x
```

#### Step 3e: Store Integrated Data
```
scenario.assumptions_used = {
    'growth_rate': 1.5,
    'gross_margin': 0.75,
    'quality_score': 1.2,
    'exit_multiple': 8.5,
    'source': 'inferred'
}
scenario.revenue_projections = [...]  # Year-by-year
scenario.final_revenue = 230_625_000
scenario.exit_value = 1_960_312_500  # Aligned!
```

### 4. **Path-to-100M Flow** (unified_mcp_orchestrator)

```
company["pwerm_scenarios"] = [scenario1, scenario2, ...]  # With integrated data
    ↓
Check if scenarios have revenue_projections:
  if scenario.revenue_projections exists:
    integrated_scenarios_available = True
    ↓
Extract revenue projections from scenarios:
  - Group scenarios by bear/base/bull (percentiles)
  - Extract revenue_projections from representative scenarios
  - Use scenario.final_revenue (already aligned with exit_value)
    ↓
Skip recalculation! Use integrated data:
  projection_data = scenario.revenue_projections  # Year-by-year
  final_revenue = scenario.final_revenue
  exit_value = scenario.exit_value  # Already aligned
    ↓
Calculate performance metrics:
  - IRR, DPI, MOIC using aligned exit_value
  - All based on same assumptions
```

## Key Benefits

### 1. **Single Source of Truth**
- All services use `intelligent_gap_filler` inferred values
- No hardcoded assumptions
- Consistent across revenue projection, cap table, exit scenarios

### 2. **Aligned Forecasts**
- Exit value = final_revenue × exit_multiple (from gap_filler)
- Revenue projections use same growth_rate as exit scenarios
- Cap table evolution uses same quality_score for step-ups

### 3. **Integrated Scenarios**
Each scenario is a complete simulation:
- Funding path → Cap table → Revenue → Exit → Returns
- All components linked and aligned
- Can trace assumptions back to source

### 4. **No Duplication**
- Path-to-100M uses revenue_projections from scenarios
- Doesn't recalculate (avoids misalignment)
- Uses aligned exit values directly

## Example: Complete Flow for One Company

```
Input: Company "Acme Corp"
  - revenue: 5M (or inferred_revenue: 5M from gap_filler)
  - stage: Series A
  - investors: ["Sequoia", "a16z"]

Step 1: Gap Filler Enrichment
  - inferred_growth_rate: 1.5 (150% YoY)
  - inferred_gross_margin: 0.75
  - quality_score: 1.3 (Tier 1 investors)

Step 2: Generate Exit Scenarios
  Scenario: "Strategic Premium Acquisition"
    - funding_path: "A→B→C"
    - Cap table: final_ownership = 0.08
    - Revenue: 5M → 230M over 5 years (using growth_rate=1.5, quality_score=1.3)
    - Exit: 230M × 8.5 = 1.96B (aligned!)
    - MOIC: 15.68x

Step 3: Path-to-100M Slide
  - Extracts revenue_projections from scenario
  - Shows: 5M → 12.5M → 28M → 59M → 121M → 230M
  - Exit point at 1.96B (aligned with revenue curve)
  - All using same assumptions
```

## Data Flow Diagram

```
┌─────────────────────┐
│  Company Data       │
│  (raw/inferred)     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ IntelligentGapFiller│
│ - infer_growth_rate │
│ - infer_margin      │
│ - quality_score     │
│ - exit_multiple     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Shared Assumptions  │
│ (single source)     │
└──────────┬──────────┘
           │
           ├─────────────────┬─────────────────┐
           ▼                 ▼                 ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────┐
│ Revenue          │ │ Cap Table    │ │ Exit Value    │
│ Projection       │ │ Evolution    │ │ Calculation   │
│                  │ │              │ │               │
│ Uses:            │ Uses:        │ │ Uses:         │
│ - growth_rate    │ │ - quality_   │ │ - final_      │
│ - quality_score  │ │   score      │ │   revenue     │
│                  │ │              │ │ - exit_       │
│                  │ │              │ │   multiple    │
└────────┬─────────┘ └──────┬───────┘ └───────┬───────┘
         │                  │                  │
         └──────────────────┼──────────────────┘
                            │
                            ▼
                 ┌──────────────────┐
                 │ Integrated       │
                 │ Scenario         │
                 │                  │
                 │ - revenue_proj   │
                 │ - cap_table      │
                 │ - exit_value     │
                 │ - all aligned!   │
                 └──────────────────┘
```

## Summary

**Before**: Services used different assumptions → misaligned forecasts
**After**: All services use shared assumptions from `intelligent_gap_filler` → aligned forecasts

The system ensures:
1. Revenue projections and exit values use the same growth assumptions
2. Cap table evolution uses the same quality score for step-ups
3. Exit values are calculated from revenue at exit (not arbitrary multiples)
4. Path-to-100M uses integrated data (no recalculation)
5. All assumptions traceable back to intelligent_gap_filler

