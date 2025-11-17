#!/bin/bash

# Download models script for Voice Agent

set -e

echo "====================================="
echo "Voice Agent - Model Downloader"
echo "====================================="
echo ""

# Create models directory
mkdir -p models

# Download Vosk Arabic model
echo "Downloading Vosk Arabic model..."
echo "This may take a few minutes..."

VOSK_MODEL="vosk-model-ar-0.22-linto"
VOSK_URL="https://alphacephei.com/vosk/models/${VOSK_MODEL}.zip"

if [ ! -d "models/${VOSK_MODEL}" ]; then
    echo "Downloading from ${VOSK_URL}"

    # Download
    wget -O "models/${VOSK_MODEL}.zip" "${VOSK_URL}" || {
        echo "Error: Failed to download Vosk model"
        echo "Please download manually from: https://alphacephei.com/vosk/models"
        exit 1
    }

    # Extract
    echo "Extracting..."
    unzip -q "models/${VOSK_MODEL}.zip" -d models/

    # Cleanup
    rm "models/${VOSK_MODEL}.zip"

    echo "Vosk model downloaded successfully!"
else
    echo "Vosk model already exists, skipping download"
fi

echo ""
echo "====================================="
echo "Model download complete!"
echo "====================================="
echo ""

# Download Whisper model (optional)
echo "Would you like to download Whisper models? (y/n)"
read -r response

if [ "$response" = "y" ] || [ "$response" = "Y" ]; then
    echo "Downloading Whisper base model..."
    python3 -c "import whisper; whisper.load_model('base')"
    echo "Whisper model downloaded!"
fi

echo ""
echo "All models ready!"
echo "You can now start the voice agent with: python main.py"
