# Remaining Tasks & Design Improvements to Remove AI-Generated Appearance

## ✅ Completed
- Dynamic text sizing system
- Content truncation with indicators
- Slide container constraints (1024x768, no scrolling)
- Chart fit (400px max height)
- Removed duplicate scoring matrix from slide 3

---

## 🔴 Critical Issues Making It Look AI-Generated

### 1. **Generic Placeholder Text**
**Problem:** Hardcoded generic text like "Analysis in progress", "Monitor for updates", "WATCH"

**Location:** `backend/app/services/unified_mcp_orchestrator.py` lines 10648-10652

**Fix:** Replace with actual analysis based on company data:
```python
# BAD (AI-generated feel):
rec["reasoning"] = "Analysis in progress"
rec["action"] = "Monitor for updates"

# GOOD (Professional):
rec["reasoning"] = f"Strong {metrics.get('Revenue Multiple', 'valuation')} multiple with {metrics.get('Growth Rate', 'growth')} growth trajectory"
rec["action"] = f"Engage with {company_name} leadership to discuss Series {next_round} timeline"
```

### 2. **Company Name Fallbacks**
**Problem:** "Company A" / "Company B" instead of actual names

**Location:** `backend/app/services/unified_mcp_orchestrator.py` lines 10669-10670

**Fix:** Better name extraction priority:
```python
# BAD:
company_a_name = company_a.get("name", "Company A")

# GOOD:
company_a_name = (
    company_a.get("company") or 
    company_a.get("name") or 
    company_a.get("company_name") or
    company_a.get("display_name") or
    "Unknown Company"  # Only as last resort
)
```

### 3. **Empty/Generic Recommendations**
**Problem:** Recommendations show "WATCH" with no real analysis

**Fix:** Generate specific recommendations based on:
- Revenue multiple vs peers
- Growth rate trajectory
- Team quality score
- Market position
- Fund fit score

### 4. **Team Quality Score = 0**
**Problem:** Shows "0/100" which looks broken

**Location:** `backend/app/services/unified_mcp_orchestrator.py` lines 10779-10800

**Fix:** Ensure minimum score calculation or hide if truly unavailable:
```python
# If team_quality is 0 or None, calculate from available data
# OR show "Data unavailable" instead of "0/100"
```

### 5. **"Unknown" Everywhere**
**Problem:** Too many "Unknown" fallbacks make it look incomplete

**Fix:** 
- Use "Not disclosed" for financials
- Use "Data unavailable" for missing analysis
- Only show fields with actual data
- Don't show empty sections at all

### 6. **Hardcoded Defaults**
**Problem:** 1M ARR default, hardcoded multipliers

**Location:** `backend/app/services/intelligent_gap_filler.py`

**Fix:** 
- Mark estimates clearly: "~$1.2M ARR (estimated)"
- Show source: "Based on team size and stage"
- Never use hardcoded defaults without indication

---

## 🎨 Design Improvements to Look Professional

### 1. **Remove Markdown Artifacts**
- No markdown syntax in rendered text
- No `**bold**` or `*italic*` in output
- Use styled components, not markdown rendering

### 2. **Better Empty States**
```typescript
// BAD:
<div>N/A</div>

// GOOD:
<div style={{ fontStyle: 'italic', color: muted }}>
  Data unavailable
</div>
```

### 3. **Specificity Over Generics**
```typescript
// BAD (AI-generated):
"Strong growth potential"

// GOOD (Professional):
"$2.1M ARR growing 180% YoY with 45% gross margins"
```

### 4. **Real Analysis, Not Placeholders**
- Calculate actual insights from data
- Show comparisons to industry benchmarks
- Provide specific next steps, not "monitor"

### 5. **Consistent Number Formatting**
- Always use $M format for millions
- Consistent decimal places
- No mixing formats (e.g., "$5M" vs "5000000")

### 6. **Professional Typography**
- Consistent font sizes (already done)
- Proper text truncation (already done)
- No cut-off letters
- Proper line heights

---

## 📋 Implementation Priority

### Phase 1: Critical (Remove AI Feel)
1. ✅ Fix company name extraction (remove "Company A/B")
2. ✅ Replace generic recommendation text
3. ✅ Fix team quality score = 0 issue
4. ✅ Remove "Analysis in progress" placeholders
5. ✅ Better empty state handling

### Phase 2: Polish (Professional Appearance)
1. ✅ Remove markdown artifacts
2. ✅ Add "estimated" indicators for inferred data
3. ✅ Improve recommendation specificity
4. ✅ Better number formatting consistency
5. ✅ Hide empty sections entirely

### Phase 3: Enhancement (Real Analysis)
1. ✅ Generate specific insights from data
2. ✅ Add industry benchmark comparisons
3. ✅ Provide actionable next steps
4. ✅ Show data sources/citations

---

## 🔧 Specific Code Changes Needed

### 1. Company Name Fix
**File:** `backend/app/services/unified_mcp_orchestrator.py:10669-10770`
```python
# Current:
company_a_name = company_a.get("name", "Company A")
company_b_name = company_b.get("name", "Company B")

# Fix:
def _get_company_name(company_data: Dict) -> str:
    """Extract company name with priority order"""
    return (
        company_data.get("company") or
        company_data.get("name") or
        company_data.get("company_name") or
        company_data.get("display_name") or
        "Unknown Company"
    )

company_a_name = _get_company_name(company_a)
company_b_name = _get_company_name(company_b)
```

### 2. Recommendation Text Fix
**File:** `backend/app/services/unified_mcp_orchestrator.py:10642-10659`
```python
# Replace generic placeholders with actual analysis
if "reasoning" not in rec:
    # Generate from actual metrics
    revenue = company_data.get("metrics", {}).get("Revenue", "N/A")
    valuation = company_data.get("metrics", {}).get("Post-Money Val", "N/A")
    rec["reasoning"] = f"Valuation of {valuation} with {revenue} revenue"
    
if "action" not in rec:
    # Generate specific next step
    stage = company_data.get("stage", "Unknown")
    rec["action"] = f"Schedule Series {stage} diligence call"
```

### 3. Team Quality Score Fix
**File:** `backend/app/services/unified_mcp_orchestrator.py:10779-10800`
```python
# Ensure minimum score or hide
if team_quality == 0 or team_quality is None:
    # Calculate from available data
    team_quality = self._calculate_team_quality_from_data(company)
    
# If still 0, don't show "0/100" - show "Data unavailable"
if team_quality == 0:
    team_quality = None  # Will be handled as unavailable
```

### 4. Remove "Unknown" Fallbacks
**File:** Multiple locations
```python
# Instead of:
stage = company.get("stage", "Unknown")

# Use:
stage = company.get("stage")
if not stage:
    # Don't include in output, or use:
    stage = None  # Frontend will handle as "Not disclosed"
```

---

## 🎯 Success Criteria

The deck should look professional when:
- ✅ No "Company A/B" - only real names
- ✅ No "Analysis in progress" - only real insights
- ✅ No "0/100" scores - either calculated or hidden
- ✅ No generic "WATCH" - specific recommendations
- ✅ No markdown artifacts - clean styled text
- ✅ No empty sections - only show what exists
- ✅ Consistent formatting - all numbers in $M format
- ✅ Real analysis - insights from actual data

