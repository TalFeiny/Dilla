#!/bin/bash

echo "🚀 GRPO Training Pipeline"
echo "=========================="

# Step 1: Check if Ollama model is available
echo "📦 Checking base model..."
if ! ollama list | grep -q "qwen2:1.5b"; then
    echo "⬇️ Downloading Qwen model..."
    ollama pull qwen2:1.5b
fi

# Step 2: Install Python dependencies
echo "📚 Installing dependencies..."
pip install -q torch transformers datasets trl peft accelerate supabase

# Step 3: Run GRPO training
echo "🧠 Starting GRPO training..."
cd backend
python3 scripts/train_grpo.py

echo "✅ GRPO training complete!"
echo ""
echo "To use your GRPO model:"
echo "1. The model is saved at: models/GRPO_CUSTOM_AGENT"
echo "2. Test it: python3 scripts/test_grpo_model.py"
echo "3. Deploy it: python3 scripts/deploy_grpo.py"