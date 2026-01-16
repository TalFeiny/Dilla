# Deck Generation Debug Plan

## Problem
- Prompt: "Compare @ExactlyAI and @CuspAI for my 345m fund with 234m to deploy"
- Getting deck with title slides only, no content
- Extraction not happening or not propagating to deck

## What We Know

### API Response
```json
{"success": false, "error": "No results generated"}
```

### Current State
1. Backend is running (uvicorn process active)
2. Supabase not configured (expected, but not blocking)
3. No request logs captured in backend.log

## Debug Strategy

### Phase 1: Verify API Communication
**Goal**: Confirm requests are reaching the backend

```bash
# Test 1: Simple health check
curl http://localhost:8000/health

# Test 2: Check if agent endpoint exists
curl http://localhost:8000/api/agent/unified-brain -X POST -H "Content-Type: application/json" -d '{"prompt": "test", "format": "deck"}' -v
```

**Expected**: Should see logs in backend.log showing the request

### Phase 2: Add Targeted Logging
**Goal**: Monitor extraction pipeline in real-time

**Key Log Points to Monitor:**

1. **Entity Extraction** (Line 1080-1124 in unified_mcp_orchestrator.py)
   - Should show: `[_extract_entities]`
   - Logs: Companies extracted from prompt
   
2. **Company Fetch** (Line 315 in unified_mcp_orchestrator.py)
   - Should show: `[_execute_company_fetch]`
   - Logs: Data fetched for each company
   
3. **Deck Generation** (Line 7349-12326 in unified_mcp_orchestrator.py)
   - Should show: `[DECK_GEN]`
   - Logs: Slide generation process

4. **Format Deck** (Line 13130-13421)
   - Should show: `[FORMAT_DECK]`
   - Logs: Final slide assembly

### Phase 3: Step-by-Step Monitoring

#### Step 1: Test Entity Extraction
```bash
# Run with verbose logging
curl -X POST http://localhost:8000/api/agent/unified-brain \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Compare @ExactlyAI and @CuspAI for my 345m fund with 234m to deploy", "format": "deck"}' \
  > response.json

# Then watch logs
tail -f backend.log | grep -E "(extract_entities|ORCHESTRATOR|COMPANY)"
```

**Check for:**
- `[_extract_entities]` logs showing companies found
- `[ORCHESTRATOR] Companies provided: X companies found`
- `[EXTRACTION]` logs for each company

#### Step 2: Test Company Fetch
**Look for:**
- `[_execute_company_fetch]` being called
- `[EXTRACTION_SUCCESS]` or `[EXTRACTION_FAILURE]` messages
- Funding rounds data

#### Step 3: Test Deck Generation
**Look for:**
- `[DECK_GEN] ⭐ _execute_deck_generation called`
- `[DECK_GEN] Starting deck generation with X companies`
- `deck-storytelling` skill execution logs

#### Step 4: Test Format Deck
**Look for:**
- `[FORMAT_DECK]` logs
- Slide generation messages
- Any fallback to `_generate_slides()`

### Phase 4: Potential Root Causes

Based on code analysis, here are the likely failure points:

#### 1. Entity Extraction Failing
**Where**: `_extract_entities()` line 1080
**Symptom**: No companies extracted from prompt
**Fix**: Add logging to see what Claude returns

#### 2. Company Fetch Not Running
**Where**: Line 315 in process_request
**Symptom**: Companies in prompt but never fetched
**Fix**: Ensure skill chain includes company-data-fetcher

#### 3. Companies Not Stored in shared_data
**Where**: Line 342-343 in process_request
**Symptom**: Companies fetched but not in shared_data
**Fix**: Check async lock and data structure

#### 4. Deck Generation Not Finding Companies
**Where**: Line 7356 in _execute_deck_generation
**Symptom**: `companies = []` when deck generation runs
**Fix**: Verify shared_data propagation

#### 5. deck-storytelling Skill Not Executing
**Where**: Skill chain execution
**Symptom**: No logs from _execute_deck_generation
**Fix**: Force-add skill to chain (already attempted at line 596)

#### 6. Fallback to Generic Slides
**Where**: Line 13244 in _format_deck
**Symptom**: Using _generate_slides() instead of real data
**Fix**: Ensure deck-storytelling result exists in results

## Immediate Action Plan

### 1. Enable Verbose Logging
Add to test command:
```bash
curl -X POST http://localhost:8000/api/agent/unified-brain \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Compare @ExactlyAI and @CuspAI for my 345m fund with 234m to deploy", "format": "deck"}' \
  2>&1 | tee curl_output.log
```

### 2. Monitor Backend Logs
In separate terminal:
```bash
tail -f backend.log | grep -E "(\[ORCHESTRATOR\]|\[EXTRACTION\]|\[DECK_GEN\]|\[COMPANY\]|ERROR)" --line-buffered
```

### 3. Check Response Structure
```bash
cat response.json | python3 -m json.tool
```

### 4. Add Debug Breakpoints
Key lines to add logging:
- Line 565: After entity extraction
- Line 587: After skill chain built
- Line 605: Before skill execution
- Line 7356: When fetching companies for deck
- Line 13244: Before format_deck call

## Success Criteria

✅ Companies extracted from prompt (@ExactlyAI, @CuspAI)
✅ Company data fetched from web search
✅ Companies stored in shared_data
✅ deck-storytelling skill executed
✅ Companies available in _execute_deck_generation
✅ Slides generated with real data
✅ NO fallback to _generate_slides()

## Next Steps

1. **Run the curl command above** and capture full output
2. **Monitor backend.log in real-time** during execution
3. **Identify where the pipeline breaks** from logs
4. **Fix the broken step** (extraction/fetch/generation/format)

