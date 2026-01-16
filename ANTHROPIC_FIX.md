# Fix Anthropic SDK - Simple Upgrade Plan

## Problem
Your `anthropic` package is version **0.8.1** but your requirements.txt wants **>=0.25.0**.
- 0.8.1 doesn't have `.messages.create()` method  
- Worked 2 days ago = probably had newer version then
- Simple fix: upgrade to match requirements

## Solution
Upgrade the package - **no code changes needed**.

Your current code in `model_router.py` (line 407) already calls:
```python
response = await self.anthropic_client.messages.create(...)
```

This will work once upgraded.

## Safe on 2016 Mac
- Anthropic SDK is just HTTP client wrapper
- No local CPU-intensive processing  
- All AI work happens on Anthropic servers
- Same dependencies, just newer version

## Steps

1. Upgrade: `cd backend && source venv/bin/activate && pip install anthropic>=0.25.0`
2. Restart backend
3. Test

That's it - no code changes.
