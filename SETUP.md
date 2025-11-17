# Setup Guide

Complete setup guide for the Voice Agent project.

## Prerequisites

- Python 3.10 or higher
- pip package manager
- 4GB RAM minimum (8GB recommended)
- Microphone and speakers for voice interaction
- Internet connection for initial setup

## Step-by-Step Setup

### 1. Install Python Dependencies

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

### 2. Install System Dependencies

#### Ubuntu/Debian

```bash
sudo apt-get update
sudo apt-get install -y \
    portaudio19-dev \
    python3-dev \
    ffmpeg \
    wget \
    unzip
```

#### macOS

```bash
brew install portaudio ffmpeg wget
```

#### Windows

Download and install:
- PyAudio wheel from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
- FFmpeg from: https://ffmpeg.org/download.html

### 3. Download Speech Recognition Models

#### Option A: Automatic Download (Recommended)

```bash
./scripts/download_models.sh
```

#### Option B: Manual Download

1. Visit: https://alphacephei.com/vosk/models
2. Download: `vosk-model-ar-0.22-linto`
3. Extract to: `models/vosk-model-ar-0.22-linto/`

### 4. Setup Local LLM (Ollama)

#### Option A: Automatic Setup

```bash
./scripts/setup_ollama.sh
```

#### Option B: Manual Setup

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
ollama serve &

# Pull a model
ollama pull llama2:7b

# Optional: Pull Arabic-optimized model
ollama pull aya:8b
```

### 5. Configure Environment

```bash
# Copy example configuration
cp .env.example .env

# Edit configuration
nano .env  # or your preferred editor
```

Key settings to verify:
- `VOSK_MODEL_PATH`: Matches your downloaded model path
- `OLLAMA_MODEL`: Matches the model you pulled
- `TTS_VOICE`: Arabic voice (ar-EG-SalmaNeural for Egyptian)

### 6. Prepare Knowledge Base

```bash
# Knowledge base directory is created automatically
# Add your documents
mkdir -p knowledge_base
echo "Your knowledge base content in Arabic" > knowledge_base/example.txt
```

### 7. Verify Installation

```bash
# Run quick verification
python -c "
import vosk
import edge_tts
import fastapi
from sentence_transformers import SentenceTransformer
print('All imports successful!')
"
```

### 8. Start the Application

```bash
# Run the server
python main.py

# You should see:
# INFO: Application startup complete
# INFO: Uvicorn running on http://0.0.0.0:8000
```

### 9. Test the Installation

Open another terminal:

```bash
# Activate virtual environment
source venv/bin/activate

# Test health endpoint
curl http://localhost:8000/api/v1/health

# Run example client
python examples/rest_api_client.py
```

## Optional Components

### GPU Acceleration (Recommended for Production)

```bash
# For NVIDIA GPUs
pip uninstall torch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Verify GPU
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

### Coqui TTS (Offline Alternative)

```bash
# Install Coqui TTS
pip install TTS

# Update .env
# TTS_ENGINE=coqui
```

### Docker Deployment

```bash
# Build Docker image
docker build -t voice-agent .

# Run container
docker run -p 8000:8000 -v ./knowledge_base:/app/knowledge_base voice-agent
```

## Troubleshooting Setup Issues

### Issue: "No module named 'vosk'"

```bash
pip install vosk
```

### Issue: "PyAudio failed to install"

Ubuntu/Debian:
```bash
sudo apt-get install portaudio19-dev
pip install pyaudio
```

macOS:
```bash
brew install portaudio
pip install pyaudio
```

Windows:
```bash
# Download wheel from https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
pip install PyAudio‑0.2.11‑cp310‑cp310‑win_amd64.whl
```

### Issue: "Ollama connection refused"

```bash
# Start Ollama service
ollama serve

# Or run in background
nohup ollama serve > ollama.log 2>&1 &
```

### Issue: "FAISS installation failed"

```bash
# Try CPU version explicitly
pip install faiss-cpu --no-cache-dir
```

### Issue: "Model download failed"

Manual download:
1. Visit: https://alphacephei.com/vosk/models
2. Download model ZIP
3. Extract to `models/` directory
4. Update `VOSK_MODEL_PATH` in `.env`

## Performance Tuning

### For Low-End Hardware

```bash
# Use smaller models
WHISPER_MODEL=tiny
OLLAMA_MODEL=llama2:7b
CHUNK_SIZE=2048

# Reduce quality for speed
TTS_ENGINE=edge
STT_ENGINE=vosk
```

### For High-End Hardware

```bash
# Use larger, more accurate models
WHISPER_MODEL=medium
OLLAMA_MODEL=llama2:13b
CHUNK_SIZE=8192

# Enable GPU acceleration
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

## Next Steps

1. Add your knowledge base documents to `knowledge_base/`
2. Customize the system prompt in `.env`
3. Test with `examples/live_microphone.py`
4. Read API documentation at http://localhost:8000/docs
5. Explore advanced configuration options

## Getting Help

- Check logs in `logs/` directory
- Review error messages carefully
- Consult README.md for usage examples
- Verify all prerequisites are installed

## Production Deployment

For production deployment:

1. Set `DEBUG=false` in `.env`
2. Configure proper logging levels
3. Set up reverse proxy (nginx)
4. Enable HTTPS
5. Configure firewall rules
6. Set up monitoring and alerting
7. Use process manager (systemd, supervisor)

Example systemd service:

```ini
[Unit]
Description=Voice Agent Service
After=network.target

[Service]
Type=simple
User=voiceagent
WorkingDirectory=/opt/voice-agent
Environment="PATH=/opt/voice-agent/venv/bin"
ExecStart=/opt/voice-agent/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Congratulations! Your Voice Agent is now set up and ready to use.
