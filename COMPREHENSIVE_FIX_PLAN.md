# COMPREHENSIVE FIX - ROOT CAUSE ANALYSIS & FIXES

## CRITICAL FINDINGS

### 1. **OLD FUND CONTEXT** (Slide 13, overall)
**ROOT CAUSE**: Hardcoded fund sizes scattered across multiple files:
- `260_000_000` in valuation_engine_service.py
- `456_000_000` in unified_mcp_orchestrator.py (fund_metrics)
- `78_000_000` in unified_mcp_orchestrator.py (fund_fit)  
- `276_000_000` in intelligent_gap_filler.py
- `100_000_000`, `200_000_000` in various places

**ACTUAL FUND** (from frontend/src/app/portfolio/pacing/page.tsx):
- Fund I (2018): $50M
- Fund II (2023): $100M
- Fund III (2024): $150M

**FIX**: Create single source of truth for fund context
```typescript
// Should come from API request context parameter:
{
  fund_size: 150_000_000,  // Actual current fund
  vintage_year: 2024,
  deployed_capital: 45_000_000,
  remaining_capital: 105_000_000,
  portfolio_count: 8,
  fund_year: 2,
  target_dpi: 3.0
}
```

### 2. **10% OWNERSHIP HARDCODED** (Slides 12, 15)
**LOCATIONS FOUND**:
- `backend/app/services/valuation_engine_service.py:1941`
- `backend/app/services/intelligent_gap_filler.py:1323`
- `backend/app/services/unified_mcp_orchestrator.py:7110`

**FIX**: Calculate from cap table or investment math, never hardcode

### 3. **365% OWNERSHIP BUG** (Slide 2)
**ROOT CAUSE**: `backend/app/services/pre_post_cap_table.py` and `company_scoring_visualizer.py`
- Adding ownership percentages instead of recalculating from scratch
- No validation that total ≤ 100%

**FIX**: Add validation, normalize percentages

### 4. **REVENUE MULTIPLES VALIDATION** (Slide 2)
**ROOT CAUSE**: `backend/app/services/intelligent_gap_filler.py:3805`
```python
trailing_multiple = valuation / revenue  # NO BOUNDS CHECK
```

**FIX**: Add validation (1x-50x typical range, flag if outside 0.5x-100x)

### 5. **STAGE CLASSIFICATION WRONG** (Slide 3)
**ROOT CAUSE**: `backend/app/services/intelligent_gap_filler.py:1968-2006`
- Not trusting extracted stage from documents
- Falling back to heuristics too quickly
- Confusion between "raised Seed" vs "raising for Series A"

**FIX**: Trust extraction first, add "current_stage" vs "raising_for_stage"

### 6. **TEAM EXTRACTION INCOMPLETE** (Slide 4)
**ROOT CAUSE**: `backend/app/services/mcp_orchestrator.py:397-448`
- Not extracting work history
- Hardcoded "lean team" text
- No technical co-founder detection

**FIX**: Enhanced extraction prompts, remove hardcoded text

### 7. **TAM "RevenueTech" NONSENSE** (Slides 6, 8)
**ROOT CAUSE**: `backend/app/services/intelligent_gap_filler.py:5066`
- Making up market categories
- No methodology shown
- Missing sources

**FIX**: Use standard market categories, show calculation method, cite sources

### 8. **GROUPED BAR CHART NOT SUPPORTED** (Slide 7)
**ROOT CAUSE**: `frontend/src/app/deck-agent/page.tsx:740`
- Chart type not implemented
- No fallback

**FIX**: Implement grouped bar or fallback to stacked bar

### 9. **CAP TABLE WRONG CHART TYPE** (Slides 9, 10, 11)
**ROOT CAUSE**: Chart selection logic choosing bar chart for ownership data
**FIX**: Use pie chart or sankey for cap tables

### 10. **EXIT SCENARIOS MESS** (Slide 12)
**ROOT CAUSE**: Multiple issues in unified_mcp_orchestrator.py
- Wrong chart type
- "return in $" label doesn't make sense
- Multiple empty charts generated
- Not accounting for future dilution

**FIX**: Single clear chart, proper labels, include dilution scenarios

### 11. **DPI CALCULATIONS** (Slide 13)
**ROOT CAUSE**: Using old fund context (see #1)
**FIX**: Use actual fund context from API request

### 12. **CONTRADICTORY RECOMMENDATIONS** (Slide 15)
**ROOT CAUSE**: Logic generating "PASS" but then saying "schedule meeting"
**FIX**: Make decision logic consistent, don't contradict yourself

### 13. **PDF/WEB DISCREPANCIES** (Slides 9-15)
**ROOT CAUSE**: `backend/app/services/deck_export_service.py`
- Different chart rendering for PDF vs web
- Some chart types skip in PDF
**FIX**: Ensure all charts render in both formats

### 14. **LLM-LOOKING FONTS/TEXT** (Slide 4, overall)
**ROOT CAUSE**: No professional design system
**FIX**: Define font system, remove AI-generated looking text

## IMPLEMENTATION ORDER (NEXT 2 DAYS)

### DAY 1: CRITICAL DATA FIXES
1. Fix fund context (1-2 hours)
2. Remove 10% hardcoding (1 hour)
3. Fix 365% ownership bug (2 hours)
4. Add revenue multiple validation (1 hour) 
5. Fix stage classification (2 hours)

### DAY 2: VISUALIZATION & POLISH
6. Enhanced team extraction (2 hours)
7. TAM methodology fixes (2 hours)
8. Chart type fixes (grouped bar, cap tables) (2 hours)
9. Exit scenarios cleanup (1 hour)
10. PDF/web consistency (1 hour)


