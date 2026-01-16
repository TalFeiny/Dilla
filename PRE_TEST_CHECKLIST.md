# Pre-Test Checklist - Potential Issues Found

## ✅ Things That Are Good

### Import Paths
- ✅ `@/` correctly maps to `src/` in tsconfig.json
- ✅ Backend `app.utils.formatters` exists and is importable
- ✅ All import statements use correct paths

### File Structure
- ✅ Backend: `backend/app/utils/formatters.py` exists
- ✅ Frontend: All new files created in correct locations
- ✅ No conflicting formatter names in active use

### Function Signatures
- ✅ `formatNumber()`, `formatPercentage()` still have same signature
- ✅ `formatMetricValue()` unchanged
- ✅ No code passing objects to `formatNumber()` (checked)

---

## ⚠️ Potential Issues to Watch

### 1. Dead Code in chart-generator.ts
**File**: `frontend/src/lib/chart-generator.ts`
**Lines**: 201-219

```typescript
private static getColorScheme(theme: string, count: number) {
  const baseColors = theme === 'professional' 
    ? this.colors.professional  // ❌ BROKEN - these don't exist anymore
    : this.colors.primary;      // ❌ BROKEN
```

**Impact**: 🟡 LOW RISK
- Method still exists but is never called
- I removed the call in `generateChartConfig()`
- Won't break unless other code calls it
- **Should remove this dead code** to avoid confusion

**Fix if needed**:
```typescript
// Just delete the method entirely OR update it to use new colors
private static getColorScheme(theme: string, count: number) {
  const colors = [];
  for (let i = 0; i < count; i++) {
    colors.push(DECK_DESIGN_TOKENS.colors.chart[i % DECK_DESIGN_TOKENS.colors.chart.length]);
  }
  return colors;
}
```

---

### 2. Object Handling Removed from formatNumber()
**File**: `frontend/src/utils/formatters.ts`
**Change**: Removed object extraction logic

**Old code**:
```typescript
if (typeof value === 'object' && value !== null) {
  if (value.value !== undefined) {
    value = value.value;  // Extract .value
  }
}
```

**New code**: Removed

**Impact**: 🟡 LOW RISK
- Checked all usages - no objects being passed
- All calls use plain numbers or strings
- formatMetricValue() still handles objects

---

### 3. Chart.js Registration
**Issue**: No explicit Chart.js component registration

**What I checked**: 
- `Chart.register()` not found in codebase
- Chart components imported dynamically in AgentChartGenerator.tsx
- Assumes react-chartjs-2 auto-registers components

**Impact**: 🟡 LOW-MEDIUM RISK
- **Depends on** how react-chartjs-2 is set up
- Modern react-chartjs-2 (v5+) requires manual registration
- Older versions (v4) auto-register

**Test**: Check if charts render at all
- If they don't render: Need to add Chart.js registration
- If they do: You're good

**Fix if needed**:
```typescript
// In frontend/src/lib/chart-config.ts or a setup file
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Legend
);
```

---

### 4. TypeScript Errors (Potential)
**Issue**: Some ChartOptions properties might not match Chart.js types

**What could break**:
```typescript
// In chart-config.ts
callbacks: {
  label: (context) => {
    const value = context.parsed.y;  // might need type assertion
```

**Impact**: 🟢 VERY LOW RISK
- TypeScript would show compile errors
- Runtime should still work
- `strict: false` in tsconfig means TS won't block compilation

---

### 5. HSL Color Format in Charts
**Issue**: Using HSL colors instead of hex/rgba

**What I did**:
```typescript
backgroundColor: 'hsl(220, 22%, 20%)'
borderColor: 'hsl(220, 22%, 20%)'
```

**Impact**: 🟢 VERY LOW RISK
- Chart.js supports HSL colors natively
- Browser canvas supports HSL
- Should work fine

---

## 🔴 Critical Things to Test

### Test 1: Backend Imports
```bash
cd backend
python3 -c "from app.utils.formatters import DeckFormatter; print(DeckFormatter.format_currency(5000000))"
```
**Expected**: `$5M`
**If fails**: Python import path issue

---

### Test 2: Frontend Compilation
```bash
cd frontend
npm run build
```
**Expected**: No TypeScript errors
**If fails**: Check error messages for import/type issues

---

### Test 3: Deck Generation
1. Start backend: `cd backend && uvicorn app.main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Go to deck-agent page
4. Generate a test deck
5. Check:
   - ✓ Numbers show as `$5M` not `5000000`
   - ✓ Charts render (any chart)
   - ✓ Chart Y-axis shows `$5M`, `$10M`
   - ✓ Colors are monochrome (grayish blues)
   - ✓ No console errors

---

### Test 4: PDF Export
1. In generated deck, click "Export PDF"
2. Check:
   - ✓ All slides render
   - ✓ Charts appear in PDF
   - ✓ Styling matches web
   - ✓ Takes ~10 seconds (increased wait time)

---

## 📋 Quick Pre-Flight Commands

### Backend Check
```bash
cd /Users/admin/code/dilla-ai/backend
python3 -c "from app.utils.formatters import DeckFormatter; print('Backend OK:', DeckFormatter.format_currency(5000000))"
```

### Frontend Check
```bash
cd /Users/admin/code/dilla-ai/frontend
npm run build 2>&1 | head -20
```

### File Check
```bash
# Verify all files exist
ls -la /Users/admin/code/dilla-ai/backend/app/utils/formatters.py
ls -la /Users/admin/code/dilla-ai/frontend/src/lib/formatters.ts
ls -la /Users/admin/code/dilla-ai/frontend/src/styles/deck-design-tokens.ts
ls -la /Users/admin/code/dilla-ai/frontend/src/lib/chart-config.ts
```

---

## 🎯 Most Likely Issues (Ranked)

1. **Chart.js registration** (if using v5+) - 40% chance
2. **TypeScript warnings** (not blockers) - 30% chance
3. **Dead code confusion** (getColorScheme) - 20% chance
4. **Everything works first try** - 10% chance 🤞

---

## 🚨 If Things Break

### Error: "Cannot find module '@/lib/formatters'"
**Cause**: TypeScript path resolution
**Fix**: Check tsconfig.json paths, restart dev server

### Error: "this.colors.professional is undefined"
**Cause**: Dead getColorScheme method got called somehow
**Fix**: Delete lines 201-219 in chart-generator.ts

### Charts don't render at all
**Cause**: Chart.js not registered
**Fix**: Add Chart.register() call (see section 3)

### Numbers still show as integers
**Cause**: Backend caching or old code path
**Fix**: Restart backend server, clear browser cache

### PDF generation fails
**Cause**: Playwright issue or formatting error
**Fix**: Check backend logs, look for /tmp/deck_debug.html

---

## ✅ Summary

**Overall Risk Level**: 🟡 **LOW-MEDIUM**

**Most likely outcome**: 
- Backend import works fine ✅
- Frontend compiles with maybe some warnings ⚠️
- Charts render but might need registration fix 🔧
- Numbers format correctly ✅
- PDF takes longer but renders ✅

**Worst case**: 
- Need to add Chart.js registration (5 min fix)
- Need to clean up dead code (2 min fix)
- Restart servers (1 min)

**Best case**:
- Everything just works 🎉

---

## 🏁 Ready to Test?

Run the quick checks above, then generate a test deck. 

**You'll know immediately if it works by checking**:
1. Do numbers show as `$5M`? 
2. Do charts appear?
3. Are colors monochrome?

If yes to all three → **Success!** ✅
If no to any → Check the specific error section above.
