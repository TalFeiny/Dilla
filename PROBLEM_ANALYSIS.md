# Deck Generator Problem Analysis

## Summary of Issues Causing Failures

### 1. **Executive Summary Bullets** ✅ FIXED
- **Location**: `_generate_executive_summary_bullets()` (line 4739)
- **Problem**: Calls `model_router.get_completion()` which can fail due to:
  - Rate limits (429 errors)
  - API timeouts
  - JSON parsing failures
- **Status**: ✅ REMOVED - No longer called

### 2. **Comparative Analysis (Portfolio Narrative)** ⚠️ FAILING
- **Location**: `_generate_comparative_analysis()` (line 4889) called at line 7963
- **Problem**: 
  - Calls `model_router.get_completion()` with large prompts
  - Can fail with rate limits or timeouts
  - Error logged as: `[DECK_GEN] ❌ CHECKPOINT 2B FAILED`
- **Impact**: Portfolio narrative slide is skipped if this fails

### 3. **Scoring Matrix** ⚠️ FAILING
- **Location**: `_generate_scoring_matrix()` (line 5948) called at line 7984
- **Problem**:
  - Calls `model_router.get_completion()` 
  - Can fail with rate limits or timeouts
  - Error logged as: `[DECK_GEN] ❌ CHECKPOINT 2C FAILED`
- **Impact**: Scoring matrix slide is skipped if this fails

### 4. **Investment Narrative** ⚠️ FAILING
- **Location**: `_generate_investment_narrative()` (line 4493) called at line 8006
- **Problem**:
  - Called for EACH company (can be 2+ calls)
  - Each calls `model_router.get_completion()`
  - High chance of rate limits with multiple companies
  - Error logged as: `[DECK_GEN] ❌ Investment narrative generation failed`
- **Impact**: Company overview slides have generic "Analysis in progress" text

### 5. **Model Router Rate Limits** ⚠️ CRITICAL
- **Location**: `backend/app/services/model_router.py` (lines 486-493)
- **Problem**:
  - Current retry logic: `await asyncio.sleep(2 ** retry)` (2s, 4s, 8s)
  - No jitter to prevent thundering herd
  - No circuit breaker for persistent rate limits
  - Rate limit errors (429) can cascade across all LLM calls
- **Impact**: All LLM-dependent slides can fail simultaneously

### 6. **Tavily Search Rate Limits** ⚠️ CRITICAL
- **Location**: `_tavily_search()` (line 2326)
- **Problem**:
  - No retry logic for 429 (rate limit) errors
  - Only retries once on SSL errors
  - Returns empty results on failure, but failures aren't retried
  - Minimum delay between requests (2s) may not be enough
- **Impact**: Company data fetching can fail, leading to empty decks

### 7. **Company Data Timing** ⚠️ POTENTIAL ISSUE
- **Location**: `_execute_deck_generation()` (line 7654)
- **Problem**:
  - Deck generation may start before companies are in `shared_data['companies']`
  - Multiple fallback strategies exist (lines 7742-7820) but may timeout
  - No explicit waiting/polling with timeout
- **Impact**: Deck generation starts with empty companies list

## Root Cause Summary

**Primary Issues:**
1. **Rate Limits**: Both Anthropic (model router) and Tavily APIs are hitting rate limits
2. **No Retry Logic**: Tavily doesn't retry on 429 errors
3. **Weak Retry Logic**: Model router has basic retry but no circuit breaker
4. **Multiple LLM Calls**: Each slide generation makes separate LLM calls, multiplying failure risk
5. **Timing Issues**: Deck generation may start before company data is ready

## Error Patterns Found

From grep results, these errors are logged:
- `[DECK_GEN] ❌ CHECKPOINT 2B FAILED` - Comparative analysis
- `[DECK_GEN] ❌ CHECKPOINT 2C FAILED` - Scoring matrix  
- `[DECK_GEN] ❌ Investment narrative generation failed` - Investment narratives
- `[DECK_GEN] ❌ All company extraction strategies failed` - No companies found
- `[DECK_GEN] ❌ CRITICAL ERROR: Deck generation failed` - Overall failure

## Recommended Fix Priority

1. ✅ **DONE**: Remove executive summary bullets
2. **HIGH**: Add Tavily retry/rate limit handling
3. **HIGH**: Enhance Anthropic rate limit handling with circuit breaker
4. **MEDIUM**: Add waiting logic for company data
5. **MEDIUM**: Make comparative analysis and scoring matrix optional/fallback
6. **LOW**: Add retry logic to investment narrative generation





















