# Feedback Status Summary

Based on your feedback files (`janfeedback.md` and `2026feedback.md`), here's the current status of missing/requested features:

## Missing/Issues Identified

### 1. **Cap Table Slide** ❌
**Feedback Reference:**
- `janfeedback.md` Slide 9: "again a fake exit scenario dummy slide. where is my cap table wtf"
- `2026feedback.md` Slide 9: "exit scenarios, empty no graph rendered"

**Current Status:**
- ✅ Code exists in `unified_mcp_orchestrator.py` (line ~10440)
- ✅ Template: `"cap_table"`
- ❓ Issue: May not be rendering correctly OR may be replaced by exit scenario slide

**Location in Code:**
- Backend: `backend/app/services/unified_mcp_orchestrator.py` lines 9706-10446
- Frontend render: `frontend/src/app/deck-agent/page.tsx` line ~2184 (cap_table handling)

---

### 2. **DPI Sankey Diagram** ⚠️
**Feedback Reference:**
- `janfeedback.md` Slide 10: "dpi sankey failed. shame because ive seen it before"
- `2026feedback.md` Slide 10: "this sankey is pretty cool but it needs to be clearer but yeah very cool, doesnt tell us enough tho, im not 100% sure whats the prices actually mean"

**Current Status:**
- ✅ Code exists: `unified_mcp_orchestrator.py` (line ~13063)
- ✅ Template: `"fund_dpi_impact_sankey"`
- ⚠️ Issue: Failing to render or data structure problems

**Location in Code:**
- Backend: `backend/app/services/unified_mcp_orchestrator.py` lines 12950-13089
- Frontend: Needs to check if template is supported

---

### 3. **Position Sizing** ❌
**Feedback Reference:**
- `janfeedback.md` Slide 14: "no entry or exit, but it came with a positio size."

**Current Status:**
- ✅ Calculation exists: `calc_position_size()` function (line ~4755)
- ❌ No dedicated slide for position sizing
- ⚠️ Position size appears in comparison metrics but not as standalone analysis

**Location in Code:**
- Calculation: `backend/app/services/unified_mcp_orchestrator.py` line ~4755
- Usage: Used in comparison slides but not as dedicated slide

---

### 4. **IRR, TVPI, DPI Contribution Metrics** ⚠️
**Feedback Reference:**
- User query: "wheres my ... dpi, position sizing and irr tvpi dpi contribution"

**Current Status:**
- ✅ Calculation exists: 
  - `PrePostCapTable.calculate_fund_performance_impact()` (lines 107-161)
  - `ValuationEngineService.calculate_fund_dpi_impact()` (line ~1709)
- ⚠️ Metrics calculated but may not be prominently displayed on slides
- ❓ Need to verify if these appear on investment recommendation or exit scenario slides

**Location in Code:**
- `backend/app/services/pre_post_cap_table.py` lines 107-161
- `backend/app/services/valuation_engine_service.py` lines 1709-1751
- Used in exit scenarios data but may not be visible on slide

---

## Slide Generation Order (Based on Code)

From `unified_mcp_orchestrator.py`, slides appear to be generated in this approximate order:

1. Title slide
2. Scoring matrix
3. Financial overview
4. Team analysis
5. Bear/bull scenarios
6. Business/product analysis
7. Power analysis (user says this is "retarded slide")
8. Breakpoint analysis
9. **Exit scenarios** (user says empty/no graph)
10. **DPI Sankey** (user says failed)
11. Follow-on strategy (user says empty)
12. Fund reasoning
13. Next round intelligence
14. **Recommendations** (user says empty but has position size)
15. Sources

---

## Next Steps

1. **Verify cap table slide rendering** - Check if template is supported in frontend
2. **Fix DPI Sankey** - Debug why it's failing (data structure or rendering issue)
3. **Add position sizing slide** - Create dedicated slide showing position sizing analysis
4. **Ensure IRR/TVPI/DPI contribution visibility** - Add these metrics prominently to relevant slides (recommendations, exit scenarios, or new slide)

---

## Files to Review

- `backend/app/services/unified_mcp_orchestrator.py` - Main deck generation logic
- `frontend/src/app/deck-agent/page.tsx` - Slide rendering
- `backend/app/services/deck_export_service.py` - PDF export (also needs work per feedback)
- `backend/app/services/pre_post_cap_table.py` - Cap table and performance metrics
- `backend/app/services/valuation_engine_service.py` - DPI impact calculations







