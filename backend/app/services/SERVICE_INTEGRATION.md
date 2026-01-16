# Service Integration Documentation

## UnifiedMCPOrchestrator Service Dependencies

This document maps all calculations in UnifiedMCPOrchestrator to their appropriate services.

## Current Service Usage

### ✅ Already Using Services:
1. **IntelligentGapFiller** (`self.gap_filler`)
   - Revenue inference: `infer_missing_data()`
   - Fund fit scoring: `score_fund_fit()`
   - Check size calculation: Built into fund fit scoring
   - Ownership targets: Part of fund economics scoring

2. **ValuationEngineService** (`self.valuation_service`)
   - PWERM calculations: `calculate_pwerm()`
   - Exit scenarios: Part of PWERM
   - Comparables analysis: `get_comparables()`
   - DCF modeling: Available via `calculate_dcf()`

3. **PrePostCapTable** (`self.cap_table_service`)
   - Cap table evolution: `calculate_cap_table()`
   - Dilution modeling: `calculate_dilution_path()`
   - SAFE conversions: Built into cap table calculations
   - Ownership tracking: Part of cap table

4. **AdvancedCapTable** (`self.advanced_cap_table`)
   - Waterfall analysis: `calculate_waterfall()`
   - Liquidation preferences: `calculate_liquidation_waterfall()`
   - Exit proceeds distribution: `calculate_exit_waterfall()`
   - Complex structures: Handles participating preferred, ratchets, etc.

5. **AdvancedDebtStructures** (Available but not yet imported)
   - Convertible notes
   - SAFEs
   - Venture debt
   - Revenue-based financing

## TODO: Service Integrations Needed

### High Priority:
1. **Line 1094**: Liquidation exit value calculation
   - Current: `company.get("total_funding", 0) * 0.5`
   - Should use: `AdvancedCapTable.calculate_liquidation_waterfall()`

2. **Lines 1189-1190**: Market sizing (TAM/SAM/SOM)
   - Current: Hardcoded percentages (10% for SAM, 1% for SOM)
   - Should use: `IntelligentGapFiller.calculate_market_sizing()`

3. **Lines 1465-1490**: Check size multipliers for AI companies
   - Current: Hardcoded multipliers based on revenue tiers
   - Should use: `IntelligentGapFiller.calculate_ai_burn_adjustment()`

4. **Lines 2165-2184**: Future round projections
   - Current: Hardcoded round sizes and dilution percentages
   - Should use: `IntelligentGapFiller.project_future_rounds()`

5. **Line 1936**: Cash balance estimation
   - Current: `funding * 0.7`
   - Should use: `IntelligentGapFiller.estimate_cash_balance()`

6. **Line 2391**: GPU cost ratio calculation
   - Current: `1 - gross_margin` with 0.3 default
   - Should use: `IntelligentGapFiller.calculate_gpu_economics()`

### Medium Priority:
1. **Lines 1519-1522**: Investment scoring weights
   - Current: Hardcoded weights (25% valuation, 35% revenue, etc.)
   - Could use: Configuration or scoring service

2. **Lines 3601-3604**: Fund capital allocation by stage
   - Current: Hardcoded percentages (20% seed, 40% A, 40% B)
   - Should use: `PrePostCapTable.optimize_capital_allocation()`

3. **Lines 2107-2108**: DPI/TVPI contribution calculations
   - Current: Simple weighted average
   - Should use: `ValuationEngineService.calculate_fund_metrics()`

## Service Method Signatures

### IntelligentGapFiller (Key Methods)
```python
- infer_missing_data(company_data: Dict) -> Dict
- score_fund_fit(company: Dict, inferred_data: Dict, fund_context: Dict) -> Dict
- calculate_market_sizing(sector: str, geography: str) -> Dict
- project_future_rounds(stage: str, total_funding: float) -> List[Dict]
- calculate_gpu_economics(business_model: str, revenue: float) -> Dict
```

### ValuationEngineService (Key Methods)
```python
- calculate_pwerm(request: ValuationRequest) -> ValuationResult
- calculate_dcf(request: ValuationRequest) -> ValuationResult
- get_comparables(company_data: Dict) -> List[ComparableCompany]
- calculate_fund_metrics(portfolio: List[Dict]) -> Dict
```

### PrePostCapTable (Key Methods)
```python
- calculate_cap_table(funding_rounds: List, current_valuation: float) -> Dict
- calculate_dilution_path(current_ownership: float, future_rounds: List) -> Dict
- convert_safes(safe_terms: Dict, priced_round: Dict) -> Dict
- optimize_capital_allocation(fund_size: float, opportunities: List) -> Dict
```

### AdvancedCapTable (Key Methods)
```python
- calculate_waterfall(exit_value: float, cap_table: Dict, preferences: List) -> Dict
- calculate_liquidation_waterfall(exit_value: float, funding_rounds: List) -> Dict
- calculate_exit_waterfall(exit_value: float, cap_table: Dict) -> Dict
- calculate_breakpoints(cap_table: Dict, preferences: List) -> List[float]
```

## Implementation Priority

1. **Critical** (Affects valuations directly):
   - Liquidation waterfall calculations
   - Future round projections
   - GPU economics for AI companies

2. **Important** (Improves accuracy):
   - Market sizing calculations
   - Cash balance estimation
   - Fund allocation optimization

3. **Nice to Have** (Enhances features):
   - Configurable scoring weights
   - Advanced debt structure integration
   - Complex preference structures

## Notes
- All hardcoded values should be replaced with service calls
- Services already exist for most calculations - just need integration
- IntelligentGapFiller is the primary service for inference and scoring
- ValuationEngineService handles all valuation methodologies
- Cap table services handle ownership and dilution
- Waterfall services handle complex liquidation preferences