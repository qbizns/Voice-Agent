# Voice Agent - Ultra-Fast Arabic Voice Conversation System

A production-ready FastAPI-based voice agent with real-time Arabic speech recognition, AI-powered responses using RAG (Retrieval-Augmented Generation), and natural text-to-speech synthesis.

## Features

- **Ultra-Fast Speech-to-Text**: Sub-100ms transcription using Vosk for real-time conversations
- **Arabic Language Support**: Full support for Arabic, including Egyptian accent
- **RAG-Powered AI Agent**: Knowledge base integration with semantic search
- **Natural Text-to-Speech**: High-quality Arabic voice synthesis with Edge TTS
- **Real-Time WebSocket**: Bidirectional streaming for instant responses
- **Local Processing**: No external API dependencies (optional Ollama for LLM)
- **Production-Ready**: Comprehensive logging, error handling, and configuration

## Architecture

```
┌──────────────┐
│  Microphone  │
└──────┬───────┘
       │ Audio Stream
       ▼
┌──────────────────┐
│   Speech-to-Text │  (Vosk/Whisper)
│   < 100ms        │
└──────┬───────────┘
       │ Text
       ▼
┌──────────────────┐
│  Knowledge Base  │  (FAISS + Embeddings)
│  Vector Search   │
└──────┬───────────┘
       │ Context
       ▼
┌──────────────────┐
│    AI Agent      │  (Ollama/Local LLM)
│  RAG Response    │
└──────┬───────────┘
       │ Response Text
       ▼
┌──────────────────┐
│ Text-to-Speech   │  (Edge TTS)
│  Natural Voice   │
└──────┬───────────┘
       │ Audio
       ▼
┌──────────────────┐
│    Speaker       │
└──────────────────┘
```

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd Voice-Agent

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Download Models

```bash
# Download Vosk Arabic model (required for STT)
./scripts/download_models.sh
```

### 3. Setup Ollama (for local LLM)

```bash
# Install and configure Ollama
./scripts/setup_ollama.sh
```

### 4. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your preferences
nano .env
```

### 5. Prepare Knowledge Base

```bash
# Create knowledge base directory
mkdir -p knowledge_base

# Add your text/markdown files to knowledge_base/
# Example:
echo "هذا مستند تجريبي في قاعدة المعرفة" > knowledge_base/example.txt
```

### 6. Run the Application

```bash
# Start the server
python main.py

# Server will be available at:
# HTTP API: http://localhost:8000
# WebSocket: ws://localhost:8000/api/v1/ws/conversation
# Documentation: http://localhost:8000/docs
```

## Usage Examples

### REST API

```python
import httpx

# Chat with AI
response = httpx.post(
    "http://localhost:8000/api/v1/chat",
    json={"message": "ما هو الطقس اليوم؟", "use_knowledge_base": True}
)
print(response.json())

# Text-to-Speech
response = httpx.post(
    "http://localhost:8000/api/v1/synthesize",
    params={"text": "مرحباً بك"}
)
with open("output.mp3", "wb") as f:
    f.write(response.content)
```

### WebSocket Real-Time Conversation

```python
import asyncio
import websockets
import json
import base64

async def conversation():
    async with websockets.connect("ws://localhost:8000/api/v1/ws/conversation") as ws:
        # Send text message
        await ws.send(json.dumps({
            "type": "text",
            "data": "مرحباً، كيف حالك؟"
        }))

        # Receive response
        response = await ws.recv()
        data = json.loads(response)
        print(f"Agent: {data['data']['text']}")

        # Get audio response
        audio_bytes = base64.b64decode(data['data']['audio'])
        with open("response.mp3", "wb") as f:
            f.write(audio_bytes)

asyncio.run(conversation())
```

### Live Microphone Conversation

```bash
# Run the live microphone example
python examples/live_microphone.py
```

## Configuration

### Environment Variables

Key configuration options in `.env`:

```bash
# Speech-to-Text
STT_ENGINE=vosk              # vosk (fast) or whisper (accurate)
VOSK_MODEL_PATH=models/vosk-model-ar-0.22-linto

# Text-to-Speech
TTS_ENGINE=edge              # edge (online) or coqui (offline)
TTS_VOICE=ar-EG-SalmaNeural  # Egyptian Arabic voice

# Knowledge Base
KNOWLEDGE_BASE_PATH=knowledge_base
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-mpnet-base-v2
TOP_K_RESULTS=3

# AI Agent
LLM_PROVIDER=ollama          # ollama or local
OLLAMA_MODEL=llama2:7b
TEMPERATURE=0.7

# System Prompt (in Arabic)
SYSTEM_PROMPT=أنت مساعد ذكي ومفيد...
```

### Performance Tuning

For ultra-fast responses:

1. **Use Vosk for STT** (10-50ms vs 100-500ms for Whisper)
2. **Enable VAD** (Voice Activity Detection) to reduce processing
3. **Optimize chunk size** based on your hardware
4. **Use local LLM** with smaller models (faster inference)
5. **Pre-load knowledge base** at startup

### Performance Benchmarks

Typical processing times on modern hardware:

| Component | Processing Time |
|-----------|----------------|
| STT (Vosk) | 10-50ms |
| STT (Whisper) | 100-500ms |
| Vector Search | 5-20ms |
| LLM Generation | 200-1000ms |
| TTS (Edge) | 100-300ms |
| **Total (Vosk)** | **315-1370ms** |
| **Total (Whisper)** | **405-1820ms** |

## API Documentation

### REST Endpoints

#### `GET /api/v1/health`
Health check endpoint

#### `POST /api/v1/transcribe`
Transcribe audio file to text
- **Input**: Audio file (WAV, MP3, etc.)
- **Output**: Transcription with confidence score

#### `POST /api/v1/synthesize`
Convert text to speech
- **Input**: Text string
- **Output**: Audio file (MP3)

#### `POST /api/v1/chat`
Chat with AI agent
- **Input**: `{"message": "...", "use_knowledge_base": true}`
- **Output**: AI response with sources

### WebSocket Protocol

Connect to: `ws://localhost:8000/api/v1/ws/conversation`

**Client Messages:**
```json
{
  "type": "audio",
  "data": "<base64_encoded_audio>"
}
```

```json
{
  "type": "text",
  "data": "your message here"
}
```

**Server Messages:**
```json
{
  "type": "transcription",
  "data": {
    "text": "...",
    "confidence": 0.95,
    "processing_time_ms": 45.2
  }
}
```

```json
{
  "type": "response",
  "data": {
    "text": "...",
    "audio": "<base64_encoded_audio>",
    "sources": ["file1.txt", "file2.txt"],
    "processing_times": {
      "transcription_ms": 45.2,
      "ai_generation_ms": 320.5,
      "synthesis_ms": 180.3,
      "total_ms": 546.0
    }
  }
}
```

## Knowledge Base

### Adding Documents

1. Create text or markdown files in `knowledge_base/`
2. Restart the application to reload documents
3. Documents are automatically chunked and embedded

### Supported Formats

- `.txt` - Plain text files
- `.md` - Markdown files
- `.text` - Text files

### Example Knowledge Base Structure

```
knowledge_base/
├── products/
│   ├── product_catalog.txt
│   └── pricing.md
├── faq/
│   ├── general_questions.txt
│   └── technical_support.md
└── policies/
    └── terms_of_service.txt
```

## Advanced Usage

### Custom System Prompts

Edit the `SYSTEM_PROMPT` in `.env` to customize AI behavior:

```bash
SYSTEM_PROMPT="أنت مساعد خدمة العملاء المتخصص في المنتجات التقنية. \
أجب بطريقة احترافية ومفيدة، واستخدم المعلومات من قاعدة المعرفة."
```

### Voice Activity Detection

Enable VAD for automatic speech detection:

```bash
VAD_ENABLED=true
VAD_AGGRESSIVENESS=3  # 0-3, higher = more aggressive
SILENCE_THRESHOLD=500  # ms of silence to end speech
```

### Multiple Voice Options

Edge TTS supports multiple Arabic voices:

```bash
# Egyptian Arabic
TTS_VOICE=ar-EG-SalmaNeural      # Female
TTS_VOICE=ar-EG-ShakirNeural     # Male

# Saudi Arabic
TTS_VOICE=ar-SA-ZariyahNeural    # Female
TTS_VOICE=ar-SA-HamedNeural      # Male
```

## Development

### Project Structure

```
Voice-Agent/
├── app/
│   ├── api/              # FastAPI routes and endpoints
│   ├── core/             # Configuration and logging
│   ├── models/           # Pydantic schemas
│   ├── services/         # Core services (STT, TTS, AI, KB)
│   └── utils/            # Utility functions
├── examples/             # Usage examples
├── scripts/              # Setup and utility scripts
├── knowledge_base/       # Knowledge base documents
├── models/               # Downloaded AI models
├── logs/                 # Application logs
├── main.py              # Application entry point
├── requirements.txt      # Python dependencies
└── .env                 # Environment configuration
```

### Running Tests

```bash
# Install dev dependencies
pip install pytest pytest-asyncio

# Run tests
pytest
```

### Code Quality

```bash
# Format code
black app/

# Lint code
ruff app/

# Type checking
mypy app/
```

## Troubleshooting

### Common Issues

**1. Vosk model not found**
```bash
./scripts/download_models.sh
```

**2. Ollama connection failed**
```bash
# Start Ollama service
ollama serve

# Or use local LLM provider
LLM_PROVIDER=local
```

**3. PyAudio installation fails**
```bash
# Ubuntu/Debian
sudo apt-get install portaudio19-dev

# macOS
brew install portaudio

# Then reinstall
pip install pyaudio
```

**4. Slow response times**
- Use Vosk instead of Whisper for STT
- Reduce `MAX_TOKENS` in .env
- Use smaller Ollama model (e.g., `llama2:7b` instead of `llama2:13b`)
- Enable VAD to reduce processing overhead

### Performance Optimization

For production deployment:

1. **Use GPU acceleration** for Whisper and local LLMs
2. **Configure Uvicorn workers** for parallel processing
3. **Set up reverse proxy** (nginx) for load balancing
4. **Cache embeddings** for frequently accessed documents
5. **Use Redis** for session management

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

For issues and questions:
- GitHub Issues: <repository-issues-url>
- Documentation: See `/docs` endpoint when running

## Acknowledgments

- **Vosk** - Fast speech recognition
- **OpenAI Whisper** - Accurate speech recognition
- **Edge TTS** - High-quality text-to-speech
- **Sentence Transformers** - Multilingual embeddings
- **FAISS** - Efficient vector search
- **FastAPI** - Modern web framework
