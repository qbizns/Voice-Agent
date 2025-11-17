#!/bin/bash

# Setup Ollama for local LLM inference

set -e

echo "====================================="
echo "Voice Agent - Ollama Setup"
echo "====================================="
echo ""

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "Ollama is not installed."
    echo "Installing Ollama..."

    # Install Ollama
    curl -fsSL https://ollama.ai/install.sh | sh

    echo "Ollama installed successfully!"
else
    echo "Ollama is already installed"
fi

# Start Ollama service
echo ""
echo "Starting Ollama service..."
ollama serve > /dev/null 2>&1 &
OLLAMA_PID=$!
sleep 5

echo "Ollama service started (PID: $OLLAMA_PID)"

# Pull recommended model
echo ""
echo "Pulling recommended model (llama2:7b)..."
ollama pull llama2:7b

echo ""
echo "You can also pull Arabic-optimized models:"
echo "  ollama pull aya:8b"
echo "  ollama pull qwen:7b"
echo ""

echo "====================================="
echo "Ollama setup complete!"
echo "====================================="
echo ""
echo "The Ollama service is running."
echo "Update your .env file to use the correct model:"
echo "  OLLAMA_MODEL=llama2:7b"
