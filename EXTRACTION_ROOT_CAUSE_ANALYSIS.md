# Extraction Root Cause Analysis

## Problem Summary

The `plan.md` fixes don't explain why companies weren't extracted at all. After investigating the code flow, here are the **actual reasons** extraction can fail:

## Root Cause 1: Israeli Company Exclusion (Line 1262-1272)

```python
# GEOGRAPHY EXCLUSION: Filter out Israeli companies
geography = (extracted_data.get('geography') or '').lower()
location = (extracted_data.get('location') or '').lower()
headquarters = (extracted_data.get('headquarters') or '').lower()

if any(term in geography for term in ['israel', 'tel aviv', 'jerusalem', 'haifa']) or \
   any(term in location for term in ['israel', 'tel aviv', 'jerusalem', 'haifa']) or \
   any(term in headquarters for term in ['israel', 'tel aviv', 'jerusalem', 'haifa']):
    logger.info(f"Excluding {company} - Israeli company")
    return {"companies": []}  # ⚠️ RETURNS EMPTY!
```

**Impact**: Any company headquartered in Israel gets filtered out and returns empty companies list.

**Solution**: Remove this exclusion or make it optional via config.

## Root Cause 2: Tavily Search Returns No Results (Lines 1190-1193)

```python
for query, result in zip(search_queries, search_results):
    if not result or not result.get("results"):
        logger.warning(f"[SEARCH][{company}] No results returned for query: {query}")
        continue  # ⚠️ SKIPS EMPTY SEARCH RESULTS
```

**Impact**: If Tavily API is down, rate-limited, or returns no results, `search_results` becomes empty.

**Impact on extraction**: `_extract_comprehensive_profile()` is called with `search_results=[]`, which means no search content for Claude to extract from.

**What happens then** (Lines 14419-14445):
```python
# Combine all search results into context
all_content = []
# ...
for result in search_results:
    # search_results is EMPTY, so all_content stays empty
combined_content = "\n\n---\n\n".join(all_content[:20])  # This is EMPTY STRING!
```

**Then Claude gets called with empty content** (lines 14474-14645):
```python
extraction_prompt = f"""Extract comprehensive structured data about {company_name} from the following search results.

Search Results:
{combined_content[:30000]}  # ⚠️ THIS IS EMPTY!
```

**Result**: Claude has nothing to extract from, so returns minimal data (just company name).

## Root Cause 3: Claude Extraction Exception Returns Minimal Data (Lines 14797-14802)

```python
except Exception as e:
    logger.error(f"Error extracting comprehensive profile for {company_name}: {e}")
    return {
        "company": company_name,
        "error": str(e)
    }  # ⚠️ RETURNS ONLY COMPANY NAME AND ERROR
```

**Impact**: If Claude extraction fails (timeout, API error, JSON parse error), the method returns a dict with only `company` and `error` fields. No funding data, no team data, nothing.

## Root Cause 4: Empty search_results Still Gets Passed to Claude (Lines 1213-1216)

```python
# Extract comprehensive profile using Claude
extracted_data = await self._extract_comprehensive_profile(
    company_name=company,
    search_results=search_results  # ⚠️ Could be EMPTY list
)
if not isinstance(extracted_data, dict):
    extracted_data = {}  # ⚠️ FALLS BACK TO EMPTY DICT

# Later...
extracted_data["prompt_handle"] = prompt_handle
# ...
return {"companies": [extracted_data]}  # ⚠️ Returns company with NO DATA
```

**Impact**: Even if Tavily returns nothing, the code still:
1. Calls `_extract_comprehensive_profile()` with empty results
2. Claude tries to extract from nothing
3. Returns a company dict with just `company`, `prompt_handle`, `requested_company` fields
4. This partial company still gets added to `shared_data["companies"]`
5. Deck generation receives companies with no funding, no team, no revenue data

## Root Cause 5: No Validation Before Adding to shared_data

The extracted company data is never validated to ensure it has minimum required fields before being added to shared_data.

## Fixes Required

### Fix 1: Remove or Make Optional Israeli Exclusion

**Location**: Line 1262-1272

```python
# OPTION A: Remove exclusion entirely
# (delete lines 1262-1272)

# OPTION B: Make it configurable
exclude_israeli = os.getenv("EXCLUDE_ISRAELI_COMPANIES", "false").lower() == "true"
if exclude_israeli:
    # ... existing exclusion code
```

### Fix 2: Log Tavily Search Results Count BEFORE Extraction

**Location**: Line 1210, add after search_results gathering

```python
# NEW: Log total search results for debugging
total_results = sum(len(r.get('results', [])) for r in search_results if r and 'results' in r)
logger.info(f"[SEARCH_SUMMARY][{company}] Total search results: {total_results}")
if total_results == 0:
    logger.error(f"[SEARCH_FAILURE][{company}] ZERO search results from Tavily! Extraction will likely return minimal data.")
```

### Fix 3: Return Error Instead of Empty Search Results

**Location**: Line 1213-1218

```python
# Extract comprehensive profile using Claude
# VALIDATE search_results first
if not search_results or all(not r.get("results") for r in search_results):
    logger.error(f"[EXTRACTION_SKIP][{company}] Skipping extraction - no search results available")
    return {"companies": []}  # Don't even try to extract from nothing

extracted_data = await self._extract_comprehensive_profile(
    company_name=company,
    search_results=search_results
)
if not isinstance(extracted_data, dict):
    extracted_data = {}

# VALIDATE extracted_data has minimum required fields
required_fields = ['business_model', 'stage', 'total_funding']
missing_fields = [f for f in required_fields if not extracted_data.get(f)]
if missing_fields:
    logger.error(f"[EXTRACTION_INCOMPLETE][{company}] Missing critical fields: {missing_fields}")
    # Still return the company so deck can generate with partial data
    # But log the issue clearly
```

### Fix 4: Better Exception Handling in _extract_comprehensive_profile

**Location**: Line 14797-14802

```python
except Exception as e:
    logger.error(f"Error extracting comprehensive profile for {company_name}: {e}")
    import traceback
    logger.error(f"Traceback: {traceback.format_exc()}")
    
    # Return minimal valid structure instead of just error
    return {
        "company": company_name,
        "business_model": "Unknown - extraction failed",
        "stage": "Unknown",
        "total_funding": 0,
        "funding_rounds": [],
        "team_size": 0,
        "revenue": 0,
        "error": str(e),
        "extraction_failed": True
    }
```

### Fix 5: Check Tavily API Key on Startup

**Location**: Line 1185 (beginning of _execute_company_fetch)

```python
# Check API key BEFORE doing searches
if not self.tavily_api_key:
    logger.error(f"[TAVILY_KEY_MISSING] Cannot fetch company data without Tavily API key")
    return {"companies": [], "error": "Tavily API key not configured"}
```

## Testing the Fixes

After implementing fixes, check logs for these patterns to diagnose extraction failures:

1. **`[TAVILY_KEY_MISSING]`** → Need to configure Tavily API key in environment
2. **`[SEARCH_FAILURE]`** → Tavily API is down or rate-limited
3. **`[EXTRACTION_INCOMPLETE]`** → Claude returned partial data
4. **`[EXTRACTION_SKIP]`** → No search results, skipping extraction

## Expected Behavior After Fixes

- If Tavily returns no results → `[EXTRACTION_SKIP]` log, returns `{"companies": []}` 
- If Claude fails to extract → Company still added with `extraction_failed: true` flag
- If Israeli company → Can configure to include/exclude
- Deck generation receives either:
  - Full company data (good)
  - Partial company data with `extraction_failed` flag (can still generate deck)
  - Empty companies list (should return error, not generic fallback)

