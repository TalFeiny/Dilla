# Review: Cap Table, Scoring Code, Recommendations, and Adjusted Gross Margin/Burn Display

## Executive Summary

This review examines:
1. ✅ **Cap Table Fixes** - Status and implementation
2. ✅ **Scoring Code** - Consistency and correctness
3. ✅ **Recommendations Consistency** - Decision logic alignment
4. ⚠️ **Adjusted Gross Margin & Burn Display** - Missing in deck slides

---

## 1. Cap Table Status ✅ FIXED

### Implementation Status
- **Frontend Fix**: `fixCapTableData()` function exists in `frontend/src/utils/chartDataFixer.ts` (lines 407-562)
- **Backend Service**: `PrePostCapTable.calculate_full_cap_table_history()` properly handles:
  - Empty funding rounds (returns initial cap table with founders)
  - Decimal to float conversion
  - Investor name extraction
  - SAFE conversions
- **Display**: Cap table is rendered in `frontend/src/app/deck-agent/page.tsx` (lines 2200-2421)
  - Uses `fixCapTableData()` before rendering
  - Handles both `investor_details` and `current_cap_table` formats
  - Shows investor ownership table with round information

### Key Fixes Applied
1. **Data Validation**: Ownership percentages clamped to 0-100%
2. **Type Coercion**: Handles number, string, and numpy types
3. **Format Handling**: Supports both `investor_details` array and `current_cap_table` dict
4. **Empty State**: Returns valid structure even when data is missing

### Code References
```407:562:frontend/src/utils/chartDataFixer.ts
export function fixCapTableData(rawData: any): FixedChartData {
  // Comprehensive cap table data fixing
  // Handles investor_details and current_cap_table formats
  // Clamps ownership to 0-100%
  // Type coercion for various data types
}
```

```2200:2421:frontend/src/app/deck-agent/page.tsx
{/* Cap Table Handling */}
{(slide.template === 'cap_table' || slide.content.sankey_data || slide.content.cap_table_data) && (
  // Uses fixCapTableData() before rendering
  // Displays investor ownership table
)}
```

**Status**: ✅ **FIXED** - Cap table data is properly fixed and displayed

---

## 2. Scoring Code Status ✅ WORKING

### Implementation
- **Service**: `CompanyScoringVisualizer.score_company()` (lines 53-146)
- **Uses**: `IntelligentGapFiller.calculate_adjusted_gross_margin()` (line 79)
- **Fund Fit Scoring**: `IntelligentGapFiller.score_fund_fit()` (lines 1495-2635)
  - Calculates component scores (stage_fit, sector_fit, unit_economics, etc.)
  - Generates overall score (0-100)
  - Returns recommendation based on score thresholds

### Scoring Logic
```2605:2616:backend/app/services/intelligent_gap_filler.py
# Generate investment recommendation
if overall_score >= 80:
    recommendation = "STRONG BUY - Excellent fit with fund thesis"
    action = "Schedule partner meeting immediately"
elif overall_score >= 65:
    recommendation = "BUY - Good fit, some concerns"
    action = "Proceed with deep diligence"
elif overall_score >= 50:
    recommendation = "HOLD - Interesting but not ideal"
    action = "Monitor and revisit next round"
else:
    recommendation = "PASS - Poor fit with fund strategy"
    action = "Pass but maintain relationship"
```

### Component Scores
- stage_fit
- sector_fit
- unit_economics
- check_size_fit
- timing_fit
- return_potential
- geography_fit
- fund_economics
- portfolio_fit

**Status**: ✅ **WORKING** - Scoring code is consistent and uses proper services

---

## 3. Recommendations Consistency ⚠️ NEEDS VERIFICATION

### Current Implementation
- **Backend**: `score_fund_fit()` generates recommendations based on score thresholds
- **Frontend**: Displays recommendations in `investment_recommendations` slide template (lines 4534-4628)

### Potential Issues
1. **Multiple Recommendation Sources**: 
   - `score_fund_fit()` returns recommendation (line 2622)
   - `CompanyScoringVisualizer` may generate separate recommendations
   - Need to verify single source of truth

2. **Frontend Display Logic**:
```4541:4561:frontend/src/app/deck-agent/page.tsx
const decision = rec.decision || rec.recommendation || '';

// Determine color scheme based on decision
if (decision.includes('BUY') || decision.includes('INVEST')) {
    bgColor = isDarkMode ? 'rgba(16, 185, 129, 0.1)' : 'rgba(16, 185, 129, 0.05)';
    textColor = isDarkMode ? '#10B981' : '#059669';
    borderColor = isDarkMode ? '#10B981' : '#059669';
} else if (decision.includes('WATCH') || decision.includes('CONSIDER')) {
    bgColor = isDarkMode ? 'rgba(251, 191, 36, 0.1)' : 'rgba(251, 191, 36, 0.05)';
    textColor = isDarkMode ? '#FBBF24' : '#D97706';
    borderColor = isDarkMode ? '#FBBF24' : '#D97706';
} else {
    bgColor = isDarkMode ? 'rgba(239, 68, 68, 0.1)' : 'rgba(239, 68, 68, 0.05)';
    textColor = isDarkMode ? '#EF4444' : '#DC2626';
    borderColor = isDarkMode ? '#EF4444' : '#DC2626';
}
```

### Recommendation Format
Backend returns:
- `recommendation`: String (e.g., "STRONG BUY", "BUY", "HOLD", "PASS")
- `action`: String (e.g., "Schedule partner meeting immediately")
- `overall_score`: Number (0-100)

**Status**: ⚠️ **NEEDS VERIFICATION** - Logic appears consistent but should verify:
1. All recommendation sources use same thresholds
2. Frontend correctly maps all recommendation types
3. No conflicting recommendations from different services

---

## 4. Adjusted Gross Margin & Burn Display ❌ NOT DISPLAYED

### Backend Calculation ✅ WORKING

#### Adjusted Gross Margin
- **Service**: `IntelligentGapFiller.calculate_adjusted_gross_margin()` (lines 3765-4041)
- **Called in**: 
  - `CompanyScoringVisualizer.score_company()` (line 79)
  - `unified_mcp_orchestrator.py` (lines 2673, 3406, 3442)
- **Returns**: 
  - `adjusted_gross_margin`: Adjusted percentage accounting for API/GPU costs
  - `base_gross_margin`: Original margin
  - `gross_margin_penalty`: Total penalty applied
  - `api_dependency_level`: API dependency assessment
  - `compute_intensity`: GPU compute intensity

#### GPU-Adjusted Burn Rate
- **Calculation**: In `unified_mcp_orchestrator.py` (lines 1848-1880)
```python
# CRITICAL: Calculate GPU-adjusted burn rate
# Low gross margin = higher burn because more GPU costs per dollar of revenue
revenue = company_data.get('revenue', 0) or company_data.get('arr', 0)
if revenue > 0:
    monthly_revenue = revenue / 12
    gross_margin = compute_data.get('gross_margin', 80) / 100
    # GPU costs = revenue * (1 - gross_margin)
    monthly_gpu_burn = monthly_revenue * (1 - gross_margin)
    
    # Add to existing burn estimate or create new one
    base_burn = company_data.get('burn_rate', 0)
    if base_burn == 0:
        # Estimate base burn from team size if available
        employees = company_data.get('employees', 10)
        base_burn = employees * 15000  # $15k/employee/month baseline
    
    # Total burn = operational burn + GPU costs
    total_burn = base_burn + monthly_gpu_burn
    company_data['burn_rate'] = total_burn
    company_data['gpu_burn'] = monthly_gpu_burn
```

### Frontend Display ❌ MISSING

**Problem**: Adjusted gross margin and GPU-adjusted burn are **NOT displayed** in deck slides.

**Current State**:
- Metrics are calculated in backend ✅
- Stored in `company_data['key_metrics']` ✅
- But **NOT rendered** in deck slides ❌

**Where They Should Be Displayed**:
1. **Key Metrics Slide**: Should show:
   - Adjusted Gross Margin (with breakdown: base margin - penalties)
   - GPU-Adjusted Burn Rate (with breakdown: base burn + GPU costs)
   - Regular burn rate (if different)

2. **Financial Analysis Slide**: Should include:
   - Gross margin analysis showing adjustments
   - Burn rate analysis showing GPU impact

**Code Reference**:
```2035:2135:frontend/src/app/deck-agent/page.tsx
{slide.content.metrics && Object.keys(slide.content.metrics).length > 0 && (
  <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mt-6">
    {Object.entries(slide.content.metrics).map(([key, value]) => {
      // This displays metrics, but adjusted_gross_margin and gpu_burn
      // are not being passed in slide.content.metrics
    })}
  </div>
)}
```

**Status**: ❌ **NOT DISPLAYED** - Need to:
1. Pass `adjusted_gross_margin` and `gpu_burn` to slide content
2. Add display logic in frontend for these metrics
3. Show breakdown (base vs adjusted) for transparency

---

## Recommendations

### 1. Cap Table ✅
**Status**: Fixed and working correctly. No action needed.

### 2. Scoring Code ✅
**Status**: Working correctly. Uses proper services and consistent logic.

### 3. Recommendations Consistency ⚠️
**Action Required**:
1. Verify all recommendation sources use same thresholds
2. Ensure single source of truth for recommendations
3. Test that frontend correctly displays all recommendation types

### 4. Adjusted Gross Margin & Burn Display ❌
**Action Required**:
1. **Backend**: Ensure `adjusted_gross_margin` and `gpu_burn` are included in slide content
   - Add to `key_metrics` in slide generation
   - Include in financial analysis slides
2. **Frontend**: Add display logic for:
   - Adjusted Gross Margin (with tooltip showing base margin and penalties)
   - GPU-Adjusted Burn Rate (with breakdown: base burn + GPU costs)
3. **Testing**: Verify metrics appear in generated decks

### Implementation Priority
1. **HIGH**: Display adjusted gross margin and burn in deck slides
2. **MEDIUM**: Verify recommendations consistency across all sources
3. **LOW**: Cap table and scoring code are working (monitor only)

---

## Summary Table

| Component | Status | Notes |
|-----------|--------|-------|
| Cap Table | ✅ FIXED | Properly fixed and displayed |
| Scoring Code | ✅ WORKING | Uses correct services, consistent logic |
| Recommendations | ⚠️ NEEDS VERIFICATION | Logic appears consistent, verify all sources |
| Adjusted Gross Margin Display | ❌ MISSING | Calculated but not shown in slides |
| GPU-Adjusted Burn Display | ❌ MISSING | Calculated but not shown in slides |









