#!/bin/bash

# Download Rhubarb Lip Sync tool

set -e

echo "====================================="
echo "Downloading Rhubarb Lip Sync"
echo "====================================="
echo ""

# Create tools directory
mkdir -p tools
cd tools

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    RHUBARB_URL="https://github.com/DanielSWolf/rhubarb-lip-sync/releases/download/v1.13.0/Rhubarb-Lip-Sync-1.13.0-Linux.zip"
    RHUBARB_ZIP="Rhubarb-Lip-Sync-1.13.0-Linux.zip"
    RHUBARB_BINARY="rhubarb"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    RHUBARB_URL="https://github.com/DanielSWolf/rhubarb-lip-sync/releases/download/v1.13.0/Rhubarb-Lip-Sync-1.13.0-macOS.zip"
    RHUBARB_ZIP="Rhubarb-Lip-Sync-1.13.0-macOS.zip"
    RHUBARB_BINARY="rhubarb"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    RHUBARB_URL="https://github.com/DanielSWolf/rhubarb-lip-sync/releases/download/v1.13.0/Rhubarb-Lip-Sync-1.13.0-Windows.zip"
    RHUBARB_ZIP="Rhubarb-Lip-Sync-1.13.0-Windows.zip"
    RHUBARB_BINARY="rhubarb.exe"
else
    echo "Unsupported OS: $OSTYPE"
    exit 1
fi

# Check if already downloaded
if [ -f "$RHUBARB_BINARY" ]; then
    echo "Rhubarb already exists at tools/$RHUBARB_BINARY"
    echo "Delete it first if you want to re-download."
    exit 0
fi

echo "Downloading from $RHUBARB_URL"
wget -O "$RHUBARB_ZIP" "$RHUBARB_URL" || {
    echo "Error: Failed to download Rhubarb"
    echo "Please download manually from: https://github.com/DanielSWolf/rhubarb-lip-sync/releases"
    exit 1
}

echo "Extracting..."
unzip -q "$RHUBARB_ZIP"

# Move binary to tools root
if [ -d "Rhubarb-Lip-Sync-1.13.0-Linux" ]; then
    mv Rhubarb-Lip-Sync-1.13.0-Linux/$RHUBARB_BINARY ./
    rm -rf Rhubarb-Lip-Sync-1.13.0-Linux
elif [ -d "Rhubarb-Lip-Sync-1.13.0-macOS" ]; then
    mv Rhubarb-Lip-Sync-1.13.0-macOS/$RHUBARB_BINARY ./
    rm -rf Rhubarb-Lip-Sync-1.13.0-macOS
elif [ -d "Rhubarb-Lip-Sync-1.13.0-Windows" ]; then
    mv Rhubarb-Lip-Sync-1.13.0-Windows/$RHUBARB_BINARY ./
    rm -rf Rhubarb-Lip-Sync-1.13.0-Windows
fi

# Make executable
chmod +x $RHUBARB_BINARY

# Cleanup
rm "$RHUBARB_ZIP"

echo ""
echo "====================================="
echo "Rhubarb Lip Sync installed!"
echo "Location: tools/$RHUBARB_BINARY"
echo "====================================="
echo ""

# Test
./$RHUBARB_BINARY --version
