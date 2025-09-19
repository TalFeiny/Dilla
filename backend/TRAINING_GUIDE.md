# GRPO Training Guide

## Current Setup ✅

### What's Working:
1. **Feedback Collection**: Frontend → Supabase (agent_feedback + preference_pairs)
2. **GRPO System**: Ready to train on examples
3. **Qwen3 Model**: Configured for tool calling and reasoning

### What's Not Automatic:
- Feedback → Training connection (by design - batch training is better!)

## Training Strategy 🎯

### Collect First, Train Later:
```bash
# Week 1-2: Collect feedback
- Users provide corrections
- System saves preference pairs
- Build up 100+ examples

# Week 2: Train
cd backend/scripts
python3 train_on_feedback.py

# Result: Improved model!
```

## How Feedback Works:

### 1. User Provides Feedback:
```javascript
// Frontend sends to /api/agent/feedback
{
  "prompt": "Analyze @Ramp",
  "response": "Simple analysis",
  "corrections": "Deep analysis with metrics...",
  "feedbackType": "edit",
  "score": 5
}
```

### 2. Saved to Supabase:
- `agent_feedback` table: Full feedback record
- `preference_pairs` table: Training data (chosen vs rejected)

### 3. Batch Training (Weekly):
```bash
# Fetch last week's feedback
python3 scripts/train_on_feedback.py

# Or train manually via API
curl -X POST http://localhost:8000/api/grpo/train
```

## Manual Training Options:

### Option 1: Train on Synthetic Data (Test)
```bash
curl -X POST http://localhost:8000/api/grpo/train-tool-calling
```

### Option 2: Check Training Stats
```bash
curl http://localhost:8000/api/grpo/tool-calling-stats
```

### Option 3: Test GRPO Ranking
```bash
curl -X POST http://localhost:8000/api/grpo/test
```

## Production Recommendations:

### Phase 1: Collection (Weeks 1-2)
- Let users provide feedback naturally
- Monitor feedback quality
- Build up 100+ preference pairs

### Phase 2: First Training (Week 2)
```bash
# Review feedback quality
SELECT * FROM preference_pairs ORDER BY created_at DESC LIMIT 20;

# Run training
python3 scripts/train_on_feedback.py
```

### Phase 3: Continuous Improvement (Ongoing)
- Weekly training runs
- A/B test improvements
- Monitor success rates

## Why This Approach Works:

1. **Quality over Speed**: Better to train on good data than train often
2. **Stability**: Users don't experience constant model changes  
3. **Efficiency**: Batch training uses resources better
4. **Control**: Can review/filter feedback before training

## Current State:
- ✅ Feedback collection working
- ✅ GRPO system ready
- ✅ Training scripts available
- ⏳ Just need to collect feedback then train!

## To Start Collecting Feedback:

1. Use the platform normally
2. Click thumbs up/down on responses
3. Provide corrections when needed
4. After 1-2 weeks, run training
5. Enjoy improved model!

---

**Bottom Line**: The system is ready. Collect feedback for 1-2 weeks, then train. This is how OpenAI, Anthropic, and others do it - batch training on quality data, not real-time training on every feedback!