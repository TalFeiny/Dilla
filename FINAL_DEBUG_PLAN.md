# Final Debug Plan

## Problem
Deck generation skips company extraction and runs PWERM immediately.

## Root Cause
1. `build_skill_chain` adds both `company-data-fetcher` (group 0) AND PWERM skills (group 1) 
2. Groups run in parallel (`asyncio.gather`)
3. PWERM can run before company extraction completes
4. PWERM uses empty/placeholder data from shared_data
5. Deck generation (group 3) has no real company data → returns empty slides

## The Fix

Make PWERM and analysis skills depend on company data extraction completing first.

```python
# In build_skill_chain, add dependencies to PWERM skills
if len(entities.get("companies", [])) > 0:
    # Make these dependent on company-data-fetcher
    chain.append(SkillChainNode(
        skill="exit-modeler",
        purpose="Model exit scenarios",
        inputs={"use_shared_data": True},
        parallel_group=1,
        depends_on=["company-data-fetcher"]  # ← Add this!
    ))
```

## Immediate Workaround

Test with a single company first to verify extraction works:
```
curl -X POST http://localhost:8000/api/agent/unified-brain \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Analyze @ExactlyAI for my 345m fund with 234m to deploy", "output_format": "analysis"}' \
  > exactlyai_analysis.json

# Then check the logs for extraction
tail -100 backend.log | grep EXTRACTION

# Then try deck
curl -X POST http://localhost:8000/api/agent/unified-brain \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Create deck for @ExactlyAI", "output_format": "deck"}' \
  > exactlyai_deck.json
```

## Next Steps
1. Add logging to confirm company fetcher IS being called
2. Add dependency constraints so PWERM waits for extraction
3. Test single company extraction first
4. Then test deck generation with real extracted data

