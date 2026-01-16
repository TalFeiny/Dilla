# Root Cause Analysis: Deck Generation Issue

## Problem Confirmed
The system is **skipping company extraction** and **going straight to PWERM calculations** without fetching real company data from the web.

## Evidence
From the curl response, I can see:
- Full PWERM scenarios being calculated
- Companies have inferred data like "business_model", "sector", etc. (likely placeholders)
- NO logs showing company extraction happening
- NO logs showing web search or data fetching

## The Bug
Looking at `backend/app/services/unified_mcp_orchestrator.py`:

The `process_request_stream` method (line 511) calls:
1. `_extract_entities` (line 565) - extracts company names from prompt
2. `build_skill_chain` (line 587) - builds execution plan
3. BUT: The skill chain is NOT including company extraction before PWERM

## Expected Flow
```
1. Extract entities → ["@ExactlyAI", "@CuspAI"]
2. For each company:
   a. Fetch from web (company-data-fetcher)
   b. Extract structured data
   c. Run PWERM with real data
3. Generate deck with results
```

## Actual Flow (BUG)
```
1. Extract entities → ["@ExactlyAI", "@CuspAI"]
2. Run PWERM with placeholder data (business_model: "AI-powered...")
3. Return PWERM results (no deck)
```

## The Fix Needed

The issue is in the skill chain building logic. We need to ensure:
1. Company data fetching happens FIRST
2. PWERM uses the fetched data
3. Deck generation uses PWERM results

Let me check where the skill chain is being built and why it's skipping extraction.

