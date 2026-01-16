# Deck Generation Issue Analysis

## Problem Summary
The system is generating fallback slides with dummy/fake data instead of real company-based deck content.

## Root Cause Analysis

### Issue 1: deck-storytelling Skill Not Executing or Not Returning Results

Looking at the logs (line 910):
```
[FORMAT_DECK] No deck-storytelling skill result found, generating fallback slides
```

The `deck-storytelling` skill is registered and should be executed, but its result is not found in `final_data` when `_format_deck()` is called.

**Code Flow:**
1. Line 758-765: `build_skill_chain()` adds `deck-storytelling` to the chain (group 3)
2. Line 596: `_execute_skill_chain()` is called
3. Line 865: Results are stored as `results[node.skill] = result`
4. Line 605: `_format_output(results, output_format, prompt)` is called
5. Lines 13028-13031: `final_data` is created by merging `shared_data` and `results`
6. Line 13157: `_format_deck(final_data)` is called
7. Line 13244: Code checks for `deck-storytelling` in data

**Problem:** The `deck-storytelling` key is not present in final_data when checked.

### Issue 2: Fallback Slide Generation Creates Generic Content

When `_format_deck()` doesn't find `deck-storytelling` results, it falls back to `_generate_slides()` which creates generic slides with limited company data.

**Evidence from logs:**
- Line 910: "No deck-storytelling skill result found"
- Line 911: "Generated 6 fallback slides" 
- The slides contain "Investment Analysis" titles and generic placeholders

### Issue 3: Companies Data Flow Issue

The logs show companies ARE being extracted:
```
[0] INFO:app.services.unified_mcp_orchestrator:[FORMAT_OUTPUT] 🏢 Companies in shared_data: 2
[0] INFO:app.services.unified_mcp_orchestrator:[FORMAT_OUTPUT] 🏢   - @Legora
[0] INFO:app.services.unified_mcp_orchestrator:[FORMAT_OUTPUT] 🏢   - @Clay
```

But the deck-storytelling skill is not receiving them or not generating slides from them.

## Detailed Investigation Points

### Checkpoint 1: Is deck-storytelling Being Called?

Looking at line 7258 in `unified_mcp_orchestrator.py`:
```python
async def _execute_deck_generation(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
    logger.info(f"[DECK_GEN] ⭐ _execute_deck_generation called with inputs: {inputs}")
```

We need to see if this log appears in the terminal output.

### Checkpoint 2: Is the Result Being Stored Correctly?

Line 865 in `_execute_skill_chain`:
```python
results[node.skill] = result
```

The result should be stored under `results["deck-storytelling"]`. This should then be included in final_data.

### Checkpoint 3: Is final_data Correctly Merged?

Lines 13028-13031:
```python
final_data = {
    **self.shared_data,
    **results
}
```

The `deck-storytelling` from `results` should override or be added to final_data.

### Checkpoint 4: Why Isn't _format_deck Finding It?

Lines 13244-13280 check for `deck-storytelling` in data and should find it if it exists.

## Possible Issues

1. **Execution Order Problem**: deck-storytelling might be executing before companies are available in shared_data
   - Line 764: It's in `parallel_group=3` which should run after companies are extracted
   - But the skill might be getting empty company lists

2. **Result Not Being Stored**: The skill might be returning a result, but it's not being stored correctly
   - Check if `_execute_deck_generation` is returning the correct format

3. **Exception Silently Caught**: The skill might be throwing an exception that's being caught somewhere
   - Check for exception handling in the skill chain execution

4. **Data Structure Mismatch**: The result from `_execute_deck_generation` might not match what `_format_deck` expects
   - Check the return value structure

## Next Steps to Investigate

1. Add logging to verify `_execute_deck_generation` is being called
2. Check if the result is being returned with the correct structure
3. Verify the result is being stored in `results["deck-storytelling"]`
4. Check if final_data contains `deck-storytelling` key before calling `_format_deck`
5. Verify companies are in shared_data when deck-storytelling runs

