#!/bin/bash

# Setup Qwen with Ollama and RL environment
echo "🚀 Setting up Qwen2.5 with RL feedback system..."

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "📦 Installing Ollama..."
    curl -fsSL https://ollama.ai/install.sh | sh
else
    echo "✅ Ollama already installed"
fi

# Pull Qwen2.5 models (multiple sizes for testing)
echo "📥 Pulling Qwen2.5 models..."
ollama pull qwen2.5:7b-instruct  # Main model
ollama pull qwen2.5:3b-instruct  # Faster option
ollama pull qwen2.5:14b-instruct # Better quality option

# Start Ollama service
echo "🔧 Starting Ollama service..."
ollama serve &

# Install Python RL dependencies
echo "📚 Installing RL dependencies..."
cd backend
pip install transformers datasets trl peft accelerate wandb
pip install ollama-python httpx

# Create model directory
mkdir -p models/qwen_rl

echo "✅ Qwen RL environment ready!"
echo "Run 'ollama list' to see available models"
echo "Run 'ollama run qwen2.5:7b-instruct' to test"