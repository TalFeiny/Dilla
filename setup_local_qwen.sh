#!/bin/bash

# Setup script for Qwen models - optimized for 30GB free space
# Total download: ~12GB, leaves 18GB free for operations

echo "🚀 Setting up Qwen models for 3-minute local execution..."
echo "📦 Total space needed: ~12GB"
echo "💾 You have 30GB free - this will work!"
echo ""

# Install Ollama if not present
if ! command -v ollama &> /dev/null; then
    echo "📥 Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo "✅ Ollama already installed"
fi

# Start Ollama service
echo "🔧 Starting Ollama service..."
ollama serve &
sleep 3

# Pull Qwen models (best quality per GB)
echo ""
echo "📥 Downloading Qwen models..."
echo "================================"

echo "1️⃣ Qwen2 1.5B (0.9GB) - Ultra fast extraction..."
ollama pull qwen2:1.5b

echo "2️⃣ Qwen2 7B (4.4GB) - General purpose excellence..."
ollama pull qwen2:7b

echo "3️⃣ Qwen2.5-Coder 7B (4.7GB) - Best code generation..."
ollama pull qwen2.5-coder:7b

echo "4️⃣ Phi-3 Mini (2.3GB) - Backup fast model..."
ollama pull phi3:mini

# Optional: Only if you have extra space
read -p "Download Mistral 7B? (4.1GB extra) [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "5️⃣ Mistral 7B (4.1GB) - Additional quality..."
    ollama pull mistral:7b
fi

echo ""
echo "✅ Setup complete! Models ready for use."
echo ""
echo "📊 Space usage:"
df -h / | grep -v Filesystem

echo ""
echo "🎯 You can now run locally in 3 minutes with:"
echo "   - Qwen2 1.5B for fast extraction (10 parallel)"
echo "   - Qwen2 7B for analysis"
echo "   - Qwen2.5-Coder for chart generation"
echo ""
echo "💡 To test: ollama run qwen2:7b"
echo "🚀 Speed settings: 0.6-0.8 recommended for 3-min target"