#!/bin/bash

# Install training environment for Mac
echo "🚀 Setting up model training environment for Mac..."

# Check Python version
python3 --version

# Install MLX for Mac (Apple Silicon optimized)
echo "📦 Installing MLX for Apple Silicon training..."
pip3 install -U mlx mlx-lm

# Install transformers and training libraries
echo "📚 Installing transformers and PEFT..."
pip3 install -U transformers datasets accelerate peft tokenizers

# Install additional dependencies
pip3 install -U bitsandbytes scipy sentencepiece protobuf

# Install torch for Mac
echo "🔥 Installing PyTorch for Mac..."
pip3 install -U torch torchvision torchaudio

# Create directories
echo "📁 Creating model directories..."
mkdir -p models/checkpoints
mkdir -p models/fine-tuned
mkdir -p data/training
mkdir -p data/feedback

echo "✅ Training environment ready!"
echo ""
echo "Next steps:"
echo "1. Run: python scripts/export_feedback.py"
echo "2. Run: python scripts/train_qwen_lora.py"
echo "3. Your fine-tuned model will be in models/fine-tuned/"