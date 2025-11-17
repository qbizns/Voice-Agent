#!/bin/bash

# Quick Start Script for Voice Agent

set -e

echo "========================================="
echo "  Voice Agent - Quick Start"
echo "========================================="
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version || {
    echo "Error: Python 3 not found. Please install Python 3.10 or higher."
    exit 1
}

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
echo "This may take a few minutes..."
pip install --upgrade pip
pip install -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Creating .env file from example..."
    cp .env.example .env
    echo "Please review and update .env file with your settings."
fi

# Create necessary directories
echo "Creating directories..."
mkdir -p models logs knowledge_base vector_store examples

# Check if Vosk model exists
if [ ! -d "models/vosk-model-ar-0.22-linto" ]; then
    echo ""
    echo "WARNING: Vosk Arabic model not found!"
    echo "Please run: ./scripts/download_models.sh"
    echo ""
fi

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo ""
    echo "WARNING: Ollama not found!"
    echo "For local LLM support, please run: ./scripts/setup_ollama.sh"
    echo ""
fi

echo ""
echo "========================================="
echo "  Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Download models: ./scripts/download_models.sh"
echo "2. Setup Ollama: ./scripts/setup_ollama.sh (optional)"
echo "3. Add documents to: knowledge_base/"
echo "4. Start server: python main.py"
echo ""
echo "For detailed setup instructions, see SETUP.md"
echo ""
