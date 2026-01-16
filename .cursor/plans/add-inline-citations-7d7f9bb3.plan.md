<!-- 7d7f9bb3-d0de-4d91-9ec2-5dd4fc37e8a1 49dc1f05-ee45-4b0a-8796-7ffd62eb29b8 -->
# Add Citations, Market Search, and Chart Rendering

## Problem Statement

1. **Missing market data**: Searches don't return market size, Gartner reports, analyst citations
2. **No trust system**: Need Perplexity-style clickable citations showing WHERE data comes from
3. **Chart rendering**: Need to verify charts work in both web view AND PDF export

## Current State Analysis

### Market Search (scripts/focused_market_search.py, market_intelligence_service.py)

- Uses Tavily API for searches
- Searches for: competitors, transactions, funding, market dynamics
- **Missing**: Specific queries for market size reports, Gartner/Forrester citations, analyst coverage

### Citations

- `CitationManager` exists in `comprehensive_deal_analyzer.py` (line 72)
- Currently tracks citations but NO clickable links or proper rendering

### Chart Rendering

- Web: Chart.js + D3 + Sankey rendering in frontend
- PDF: **Playwright + Chromium** renders HTML with Chart.js to PDF (line 3716-3850)
- PPTX: python-pptx charts
- **Status**: ALREADY FULL FIDELITY! Uses Playwright to render actual Chart.js charts, not reportlab basics

## Implementation Plan

### 1. Enhance Market Search Queries

**File**: `backend/app/services/market_intelligence_service.py`

Add specific queries for analyst reports and market sizing:

```python
# New queries to add:
f"{sector} market size Gartner Forrester IDC report 2024"
f"{sector} TAM SAM SOM market sizing analyst report"
f"{company_name} Gartner Magic Quadrant position"
f"{sector} industry analysis McKinsey BCG Bain"
f"{sector} market forecast CAGR growth projection 2025-2030"
```

**File**: `scripts/focused_market_search.py` (line 34-56)

Add to queries list:

- Market sizing from analyst firms
- Gartner/Forrester/IDC reports
- Industry research reports with URLs

### 2. Extract Citations from Search Results

**File**: `backend/app/services/market_intelligence_service.py`

When processing Tavily results, extract:

- Source URL (tavily returns this)
- Source title (e.g., "Gartner Report: AI Market Size 2024")
- Relevant quote/data point
- Publication date

Store as:

```python
{
  "claim": "AI market size is $50B",
  "source_title": "Gartner Market Report 2024",
  "source_url": "https://gartner.com/...",
  "date": "2024-09-15"
}
```

### 3. Update LLM Prompts to Include Citations

**File**: `backend/app/services/unified_mcp_orchestrator.py` (line 12847)

Modify `_generate_comprehensive_business_analysis` prompt:

```python
prompt = f"""...
IMPORTANT: For each claim, include inline citation [1], [2], [3].

Available sources:
{json.dumps(available_citations, indent=2)}

Use these sources and add inline citations like:
- "Market growing at 40% YoY [1]"
- "Company has $50K ACV based on pricing model [2]"

Return JSON:
{{
  "analysis": "text with [1] [2] [3] citations",
  "citations_used": [1, 2, 3]
}}
"""
```

### 4. Build Citation System with URLs

**File**: `backend/app/services/citation_manager.py` (enhance existing)

```python
class CitationManager:
    def add_citation(self, claim: str, source_url: str, source_title: str):
        # Add citation and return citation number [1], [2], etc.
        
    def get_citations_html(self) -> str:
        # Return formatted HTML with clickable links
        # [1] <a href="url">Source Title</a>
        
    def get_citations_for_slide(self, slide_id: str) -> List[Dict]:
        # Return citations used in this slide
```

### 5. Frontend: Render Clickable Citations

**File**: Frontend slide components

Add Sources section at bottom of each slide:

```tsx
<div className="sources">
  <h4>Sources</h4>
  {citations.map(c => (
    <div key={c.id}>
      [{c.id}] <a href={c.url} target="_blank">{c.title}</a>
    </div>
  ))}
</div>
```

### 6. PDF Export: Include Citations

**File**: `backend/app/services/deck_export_service.py` (line 4379+)

Add citations to PDF slides:

- Render as footnotes at bottom of each slide
- Include clickable URLs in PDF (reportlab supports hyperlinks)
- Small font, gray color

### 7. Verify Chart Rendering

**Files to check**:

- `backend/app/services/deck_export_service.py` (line 4379-4422) - PDF charts
- `frontend/src/app/api/export/deck/route.ts` (line 48) - includes charts flag
- Frontend chart rendering components

**Test**: Generate deck → verify charts show in web → export PDF → verify charts in PDF

## API Call Strategy

**Market search**: 1 batch of Tavily searches per deck (already doing this)

**LLM commentary**: 2-3 calls total (already doing this)

- 1 call: Business analysis with citations
- 1 call: Competitive landscape with citations

**Total new calls**: ~5-10 Tavily searches (for market sizing/analyst reports)

## Expected Outcome

Deck will have:

- "AI market size is $50B with 40% CAGR [1]"
- "Company positioned in Gartner Leaders quadrant [2]"
- "Comparable transactions at 8-12x revenue [3]"

Sources section:

```
[1] Gartner: AI Market Analysis 2024 (clickable link)
[2] Company website - Product pricing (clickable link)
[3] PitchBook: Recent M&A Transactions (clickable link)
```

Charts render perfectly in both web and PDF.

### To-dos

- [ ] Enhance CitationManager to track data sources and generate inline citation markers
- [ ] Update LLM prompts in _generate_comprehensive_business_analysis to request inline citations
- [ ] Add citations to competitive landscape analysis (_generate_competitive_landscape_analysis)
- [ ] Add Sources section to slide rendering components in frontend