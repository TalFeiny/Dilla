#!/bin/bash

# Complete training pipeline for YOUR custom agent model

echo "🚀 Training YOUR Custom Agent Model"
echo "===================================="

# Step 1: Install dependencies
echo ""
echo "📦 Installing training dependencies..."
pip3 install -q torch transformers peft datasets accelerate

# Step 2: Export your feedback from Supabase
echo ""
echo "📊 Exporting your feedback data..."
cd backend
python3 scripts/export_feedback.py

# Step 3: Train YOUR model on YOUR feedback
echo ""
echo "🧠 Training on YOUR feedback (this creates YOUR weights)..."
python3 scripts/train_custom_agent_model.py

# Step 4: Test YOUR trained model
echo ""
echo "🧪 Testing YOUR custom model..."
python3 app/services/deploy_custom_weights.py

echo ""
echo "✅ Training complete!"
echo ""
echo "YOUR custom model is now ready at: models/MY_CUSTOM_AGENT"
echo ""
echo "To use it:"
echo "1. Restart your backend: cd backend && uvicorn app.main:app --reload"
echo "2. Your app will automatically use YOUR model instead of Claude"
echo ""
echo "The model has learned from YOUR feedback and implements YOUR decision-making!"