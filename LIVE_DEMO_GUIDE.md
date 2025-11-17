# `/live` Real-Time Voice Demo - Complete Guide

Production-grade single-page web UI for real-time voice interaction with the Voice Agent backend.

## Overview

The `/live` demo provides a **visually impressive, full-screen web interface** that:
- ✅ Streams microphone audio in real-time to the backend
- ✅ Displays live circular waveform visualization
- ✅ Shows transcription and AI responses as they arrive
- ✅ Plays back synthesized speech
- ✅ Tracks performance metrics
- ✅ Requires zero build tools (pure HTML/CSS/JS)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (HTML+JS)                    │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────┐ │
│  │getUserMedia()│──→│Web Audio API │──→│  Canvas    │ │
│  │              │   │(AnalyserNode)│   │ Visualizer │ │
│  └──────────────┘   └──────────────┘   └────────────┘ │
│          │                                              │
│          │ 16kHz Mono PCM16                             │
│          ▼                                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │    WebSocket Client (ws://host:8000/live)       │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────┬───────────────────────────────┘
                          │ JSON Messages
                          │
┌─────────────────────────▼───────────────────────────────┐
│              FastAPI Backend (Python)                   │
│  ┌──────────────────────────────────────────────────┐  │
│  │  WebSocket /live                                 │  │
│  │  ┌────────┐  ┌──────┐  ┌─────┐  ┌─────┐        │  │
│  │  │ Buffer │─→│ STT  │─→│ AI  │─→│ TTS │        │  │
│  │  │ Audio  │  │(Vosk)│  │Agent│  │Edge │        │  │
│  │  └────────┘  └──────┘  └─────┘  └─────┘        │  │
│  └──────────────────────────────────────────────────┘  │
│                          │                              │
│                          ▼                              │
│        JSON Responses (transcription, response)         │
└─────────────────────────────────────────────────────────┘
```

---

## Message Protocol

### Client → Server Messages

#### 1. Start Session

```json
{
  "type": "start",
  "data": {
    "language": "ar",
    "session_id": "unique_id_here",
    "sample_rate": 16000,
    "channels": 1
  }
}
```

**When:** Sent immediately after WebSocket connection opens.
**Purpose:** Initialize a new voice session.

#### 2. Audio Chunk

```json
{
  "type": "audio_chunk",
  "data": {
    "sample_rate": 16000,
    "channels": 1,
    "pcm16": "<base64_encoded_pcm16_data>"
  }
}
```

**When:** Sent every ~400ms while user is speaking.
**Format:** 16-bit PCM, mono, 16kHz, base64-encoded.
**Example:** 400ms chunk = 6400 samples × 2 bytes = 12,800 bytes → ~17KB base64.

#### 3. End Utterance

```json
{
  "type": "end"
}
```

**When:** User stops speaking (controlled by stop button).
**Purpose:** Signal backend to process complete audio buffer.

---

### Server → Client Messages

#### 1. Session Started

```json
{
  "type": "session_started",
  "data": {
    "session_id": "live_1234567890"
  }
}
```

**When:** Response to `start` message.
**Purpose:** Confirm session is ready.

#### 2. Transcription

```json
{
  "type": "transcription",
  "data": {
    "text": "ما هي السرعة القصوى لدبابة إم1 إيه1؟",
    "is_final": true,
    "confidence": 0.95
  }
}
```

**When:** After processing complete audio (on `end` signal).
**Purpose:** Show user what was understood from speech.

#### 3. Response (Final)

```json
{
  "type": "response",
  "data": {
    "text": "السرعة القصوى لدبابة إم1 إيه1 على الطرق الممهدة تقريباً 67 كم/ساعة",
    "audio": "SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAA...",
    "sources": ["m1a1_abrams.md", "structured_knowledge"],
    "processing_times": {
      "transcription_ms": 45.3,
      "ai_generation_ms": 120.5,
      "synthesis_ms": 180.2,
      "total_ms": 346.0
    }
  }
}
```

**When:** After AI processing + TTS.
**Purpose:** Deliver final answer with synthesized speech.

#### 4. Error

```json
{
  "type": "error",
  "data": {
    "message": "No speech detected in audio"
  }
}
```

**When:** On any error condition.
**Purpose:** Inform user of issues.

---

## Complete Message Flow Example

### Scenario: User asks about M1A1 Abrams tank speed

```
┌──────────────┐                                  ┌──────────────┐
│   Browser    │                                  │   Backend    │
└──────┬───────┘                                  └──────┬───────┘
       │                                                 │
       │ [User clicks "ابدأ المحادثة"]                  │
       │                                                 │
       │  WebSocket Connect                              │
       │────────────────────────────────────────────────>│
       │                                                 │
       │  {"type": "start", ...}                         │
       │────────────────────────────────────────────────>│
       │                                                 │
       │                 {"type": "session_started", ...}│
       │<────────────────────────────────────────────────│
       │                                                 │
       │ [User speaks: "ما هي السرعة القصوى..."]        │
       │ [Audio captured: 0.4s chunk]                    │
       │                                                 │
       │  {"type": "audio_chunk", "data": {...}}         │
       │────────────────────────────────────────────────>│
       │                                                 │ [Buffer: 6400 samples]
       │ [Audio captured: 0.4s chunk]                    │
       │                                                 │
       │  {"type": "audio_chunk", "data": {...}}         │
       │────────────────────────────────────────────────>│
       │                                                 │ [Buffer: 12800 samples]
       │ [... more chunks ...]                           │
       │                                                 │
       │ [User stops speaking]                           │
       │                                                 │
       │  {"type": "end"}                                │
       │────────────────────────────────────────────────>│
       │                                                 │
       │                                                 │ [STT Processing...]
       │                                                 │ [45ms] Vosk transcribes
       │                                                 │
       │          {"type": "transcription", ...}         │
       │<────────────────────────────────────────────────│
       │                                                 │
       │ [Display: "ما هي السرعة القصوى..."]            │
       │                                                 │
       │                                                 │ [AI Processing...]
       │                                                 │ [120ms] Structured KB match
       │                                                 │ [180ms] Edge TTS synthesis
       │                                                 │
       │                {"type": "response", ...}        │
       │<────────────────────────────────────────────────│
       │                                                 │
       │ [Display: "السرعة القصوى 67 كم/ساعة"]          │
       │ [Decode base64 audio → Play]                    │
       │ [Show metrics: Total 346ms]                     │
       │                                                 │
```

**Total Latency:** ~400ms from "end" to audio playback start.

---

## Setup & Usage

### 1. Start the Server

```bash
cd /path/to/Voice-Agent
python main.py
```

**Expected logs:**
```
INFO: All services initialized successfully!
INFO: Server ready at http://0.0.0.0:8000
INFO: Live demo page: http://0.0.0.0:8000/live
```

### 2. Open the Demo Page

```bash
# In browser, navigate to:
http://localhost:8000/live
```

### 3. Use the Interface

**Step 1:** Click **"🎤 ابدأ المحادثة"**
- Browser will request microphone permission
- Click "Allow"

**Step 2:** Start speaking in Arabic
- Waveform visualizer will animate with your voice
- Recording indicator shows "● RECORDING"

**Step 3:** Click **"⏹️ إيقاف"** when done
- Backend processes your speech
- Transcription appears in top-right card
- AI response appears in bottom-right card
- Audio response plays automatically
- Performance metrics displayed

**Step 4:** Repeat as needed
- Click "🎤 ابدأ المحادثة" again for next question

---

## Audio Technical Specifications

### Client-Side (Browser)

**Capture:**
- Format: PCM16 (16-bit signed integer)
- Sample Rate: 16,000 Hz (16kHz)
- Channels: 1 (mono)
- Chunk Size: 6,400 samples (400ms @ 16kHz)
- Chunk Bytes: 12,800 bytes (6400 × 2)
- Encoding: Base64 for WebSocket JSON transport

**Processing Chain:**
```
Microphone
    ↓
getUserMedia() (browser API)
    ↓
AudioContext (sampleRate: 16000)
    ↓
MediaStreamSource
    ├─→ AnalyserNode → Canvas (visualization)
    └─→ ScriptProcessor (4096 buffer)
         ↓
    Convert Float32 → Int16
         ↓
    Buffer until 6400 samples
         ↓
    Base64 encode
         ↓
    WebSocket.send()
```

### Server-Side (Python)

**Receive:**
- Decode base64 → bytes
- Buffer chunks in memory
- On "end" signal: assemble complete audio

**Format Conversion:**
```python
# Client sends: base64(PCM16 bytes)
pcm16_base64 = message["data"]["pcm16"]
pcm16_bytes = base64.b64decode(pcm16_base64)

# pcm16_bytes is now raw audio:
# - 16-bit signed integers (little-endian)
# - Ready for STT processing
```

**STT Processing:**
```python
# Vosk/Whisper expect raw audio bytes
audio_data = session.get_audio_data()  # Complete buffer
text, confidence, time_ms = await stt_service.transcribe(audio_data)
```

---

## Performance Optimization

### Client-Side

**Chunk Size Trade-off:**
- **Smaller chunks (200ms):** Lower latency, more network overhead
- **Larger chunks (600ms):** Higher latency, less overhead
- **Recommended: 400ms** (good balance)

**Network Optimization:**
```javascript
// Current: Send every 400ms
// For lower latency: Send every 200ms
const CHUNK_DURATION_MS = 200;  // Adjust this
```

### Server-Side

**Concurrent Processing:**
```python
# Audio buffering is instant (no processing)
# Real processing happens on "end" signal

# Pipeline (sequential):
1. STT: 45ms (Vosk) or 200ms (Whisper)
2. AI:  120ms (structured) or 500ms (RAG+LLM)
3. TTS: 180ms (Edge TTS)

Total: 345ms - 880ms typical
```

**Optimization Strategies:**
1. **Use Vosk** instead of Whisper (5-10× faster)
2. **Enable structured knowledge** for common queries
3. **Pre-warm services** (already done in lifespan)
4. **Use faster LLM** (smaller Ollama model)

---

## UI Customization

### Change Theme Colors

In `live.html`, modify CSS variables:

```css
/* Current gradient: Blue → Purple */
background: linear-gradient(135deg, #00d4ff, #7000ff);

/* Alternative: Green → Blue */
background: linear-gradient(135deg, #00ff88, #00d4ff);

/* Alternative: Red → Orange */
background: linear-gradient(135deg, #ff4444, #ff8800);
```

### Change Waveform Style

**Current:** Circular oscilloscope

**Alternative:** Bar visualizer (replace `visualize()` function):

```javascript
function visualize() {
    if (!isRecording || !analyser) return;
    requestAnimationFrame(visualize);

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    analyser.getByteFrequencyData(dataArray);  // Changed to frequency

    ctx.fillStyle = 'rgba(10, 14, 39, 0.3)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const barWidth = (canvas.width / bufferLength) * 2.5;
    let barHeight;
    let x = 0;

    for (let i = 0; i < bufferLength; i++) {
        barHeight = dataArray[i] / 255 * canvas.height;

        const gradient = ctx.createLinearGradient(0, canvas.height, 0, 0);
        gradient.addColorStop(0, '#00d4ff');
        gradient.addColorStop(1, '#7000ff');
        ctx.fillStyle = gradient;

        ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);
        x += barWidth + 1;
    }
}
```

### Add Language Selector

```html
<!-- Add before start button -->
<select id="languageSelect" style="...">
    <option value="ar">العربية</option>
    <option value="en">English</option>
</select>
```

```javascript
// Update in connectWebSocket()
const language = document.getElementById('languageSelect').value;
const startMsg = {
    type: 'start',
    data: {
        language: language,  // Use selected language
        ...
    }
};
```

---

## Troubleshooting

### "Microphone access denied"

**Cause:** User clicked "Block" on permission prompt.

**Fix:**
1. Click lock icon in browser address bar
2. Reset microphone permission
3. Reload page and click "Allow"

### "WebSocket connection failed"

**Cause:** Backend not running or wrong URL.

**Fix:**
```bash
# Check backend is running
curl http://localhost:8000/api/v1/health

# Check logs
tail -f logs/voice_agent_*.log

# Restart server
python main.py
```

### "No speech detected"

**Cause:** Audio too quiet or silence.

**Fix:**
1. Check mic volume in system settings
2. Speak louder/closer to mic
3. Test mic in another app first
4. Check browser mic permissions

### "Waveform not showing"

**Cause:** Canvas size issue or recording not started.

**Fix:**
```javascript
// In browser console:
console.log('Recording:', isRecording);
console.log('Analyser:', analyser);
console.log('Canvas size:', canvas.width, canvas.height);

// Refresh page if canvas.width = 0
```

### "Audio response not playing"

**Cause:** Base64 decoding error or audio format issue.

**Fix:**
```javascript
// Check in browser console:
// Should see: "Playing audio response..."
// Check for errors in console

// Test manual decode:
const testAudio = new Audio('data:audio/mpeg;base64,' + response.data.audio);
testAudio.play();
```

---

## Browser Compatibility

### Tested Browsers

| Browser | Version | Status |
|---------|---------|--------|
| Chrome | 90+ | ✅ Full support |
| Firefox | 88+ | ✅ Full support |
| Safari | 14+ | ✅ Full support |
| Edge | 90+ | ✅ Full support |
| Mobile Chrome | 90+ | ✅ Works (touch UI) |
| Mobile Safari | 14+ | ⚠️ Requires user gesture |

### Known Limitations

**iOS Safari:**
- Requires user tap to start audio (cannot auto-play)
- getUserMedia requires HTTPS (or localhost)

**Firefox:**
- ScriptProcessor deprecated (use AudioWorklet in future)

**All browsers:**
- getUserMedia requires HTTPS in production
- Localhost/127.0.0.1 works without HTTPS

---

## Production Deployment

### 1. HTTPS Required

```nginx
# nginx config
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

### 2. CORS Configuration

```python
# In main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],  # Specific domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 3. Environment Variables

```bash
# Production .env
DEBUG=false
LOG_LEVEL=WARNING
HOST=127.0.0.1  # Bind to localhost only
PORT=8000
```

### 4. Process Management

```bash
# Using systemd
sudo systemctl start voice-agent
sudo systemctl enable voice-agent

# Using supervisor
supervisorctl start voice-agent
```

---

## Advanced Features

### Multi-Language Support

Modify backend to detect language:

```python
# In live_routes.py
language = message.get("data", {}).get("language", "ar")

# Pass to STT
if language == "en":
    # Use English model
    pass
else:
    # Use Arabic model (default)
    pass
```

### Voice Activity Detection (VAD)

Add client-side silence detection:

```javascript
// Detect silence and auto-send "end"
let silenceStart = null;
const SILENCE_THRESHOLD = 128;  // Adjust
const SILENCE_DURATION = 1500;  // 1.5s silence = end

scriptProcessor.onaudioprocess = (e) => {
    const inputData = e.inputBuffer.getChannelData(0);

    // Calculate RMS (volume)
    const rms = Math.sqrt(
        inputData.reduce((sum, val) => sum + val * val, 0) / inputData.length
    ) * 128;

    if (rms < SILENCE_THRESHOLD) {
        if (!silenceStart) silenceStart = Date.now();

        if (Date.now() - silenceStart > SILENCE_DURATION) {
            // Auto-send end
            ws.send(JSON.stringify({ type: 'end' }));
            silenceStart = null;
        }
    } else {
        silenceStart = null;
    }

    // ... rest of processing
};
```

### Session Analytics

Track usage metrics:

```python
# In LiveSession class
self.metrics = {
    "chunks_received": 0,
    "total_bytes": 0,
    "duration_seconds": 0,
    "queries_processed": 0
}

# Log on session close
logger.info(f"Session {self.session_id} metrics: {json.dumps(self.metrics)}")
```

---

## Example Queries to Test

### Technical Questions
- "ما هي السرعة القصوى لدبابة إم1 إيه1؟"
- "كم عدد أفراد طاقم الدبابة؟"
- "ما هو عيار المدفع الرئيسي؟"

### General Questions
- "من أنت؟"
- "ماذا يمكنك أن تفعل؟"
- "أخبرني عن قدراتك"

### Complex Questions
- "قارن بين دبابة إم1 إيه1 وإم1 إيه2"
- "اشرح منظومة السيطرة على النيران"

---

## Support & Debugging

### Enable Verbose Logging

**Client-side (browser console):**
```javascript
// Already enabled - check console for:
// - WebSocket messages
// - Audio chunk info
// - Errors
```

**Server-side:**
```bash
# In .env
LOG_LEVEL=DEBUG

# Restart and check logs
tail -f logs/voice_agent_*.log | grep "live"
```

### Monitor WebSocket Traffic

```bash
# Chrome DevTools
1. F12 → Network tab
2. Filter: WS
3. Click /live connection
4. See all messages in Messages tab
```

---

## Summary

The `/live` demo provides a **production-ready, zero-build, single-page interface** for real-time voice interaction with your AI agent.

**Key metrics:**
- 🚀 **400ms chunks** for smooth streaming
- ⚡ **<1s total latency** (for simple queries with structured KB)
- 🎨 **Modern dark UI** with live visualizations
- 📱 **Mobile-friendly** (with touch support)
- 🔒 **Secure** (HTTPS ready for production)

Ready to deploy and impress! 🎉
