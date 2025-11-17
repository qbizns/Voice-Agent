# Unity Client for Voice Agent with Lip-Sync

Complete Unity implementation for connecting to the FastAPI Voice Agent backend with real-time lip-sync.

## Prerequisites

- **Unity 2021.3 LTS or newer** (tested on 2021.3+)
- **Target platforms**: PC, Mac, Android, VR (Quest/PCVR)
- **Required Unity packages**:
  - `com.unity.nuget.newtonsoft-json` (for JSON parsing)
- **Character requirements**:
  - Character with `SkinnedMeshRenderer` containing face blendshapes
  - Minimum 9 blendshapes for Rhubarb visemes (A, B, C, D, E, F, G, H, X)

## Installation

### 1. Import Scripts

Copy all C# scripts from `Unity/Scripts/` to your Unity project:

```
Assets/
└── Scripts/
    └── VoiceAgent/
        ├── Data/
        │   ├── VoiceAgentMessages.cs
        │   └── VisemeMapping.cs
        ├── Networking/
        │   └── VoiceAgentClient.cs
        ├── Audio/
        │   └── AudioStreamPlayer.cs
        └── LipSync/
            └── LipSyncController.cs
```

### 2. Install Dependencies

#### NativeWebSocket

Add to `manifest.json`:
```json
{
  "dependencies": {
    "com.endel.nativewebsocket": "https://github.com/endel/NativeWebSocket.git#upm"
  }
}
```

#### NAudio for MP3 Decoding (Windows/Standalone only)

For standalone builds, you can use NAudio. For cross-platform, configure backend to send WAV instead.

Download `NAudio.dll` and place in `Assets/Plugins/`.

**Or** configure backend to send WAV:
- Set `audio_format="wav"` in lipsync_service.generate_visemes()
- Modify EdgeTTSEngine to output WAV (Edge TTS outputs MP3 by default, so you may need conversion)

### 3. Scene Setup

#### Step 1: Create Voice Agent Manager

1. Create empty GameObject: `VoiceAgentManager`
2. Add component: `VoiceAgentClient`
3. Configure in Inspector:
   - **Server URL**: `ws://your-server:8000/api/v1/ws/conversation`
   - **Auto Connect**: true (or false if manual control)

#### Step 2: Setup Character with Lip-Sync

1. Import your character with face blendshapes
2. Select the GameObject with `SkinnedMeshRenderer` (usually head/face mesh)
3. Add component: `LipSyncController`
4. Configure blendshape mapping (see below)

#### Step 3: Add Audio Source

1. Add `AudioSource` component to character (or separate GameObject)
2. Configure:
   - **Spatial Blend**: 0 (2D) or 1 (3D) based on your needs
   - **Play On Awake**: false

#### Step 4: Wire Components

On `VoiceAgentClient`:
- **Lip Sync Controller**: Drag your LipSyncController GameObject
- **Audio Source**: Drag your AudioSource GameObject

## Blendshape Mapping

### Rhubarb Viseme Set (9 visemes)

Map Unity blendshapes to Rhubarb visemes:

| Viseme ID | Description | Example Sounds | Unity Blendshape Name (Example) |
|-----------|-------------|----------------|----------------------------------|
| A | Open mouth | "a" in father | `mouthOpen`, `jawOpen` |
| B | Lips together | b, p, m | `mouthClosed`, `lipsPucker` |
| C | Tight lips | s, z | `mouthSmile`, `lipsPress` |
| D | Teeth visible | th (voiced/unvoiced) | `mouthFunnel` |
| E | Lips & teeth | f, v | `lipsLowerDown` |
| F | Lower lip raised | f, v | `lipsLowerUp` |
| G | Back tongue raised | k, g | `mouthShrugUpper` |
| H | High front tongue | ee, i | `mouthSmileLeft`/`Right` |
| X | Rest/silence | silence | (neutral, weight 0) |

### Mapping in Inspector

In `LipSyncController`:

1. Set **Viseme Count** = 9
2. For each viseme (A, B, C, D, E, F, G, H, X):
   - **Viseme ID**: Enter the letter (A, B, C, etc.)
   - **Blendshape Index**: Find the corresponding blendshape index in your SkinnedMeshRenderer

**How to find blendshape index:**
```csharp
// Temporary script to print blendshape indices
for (int i = 0; i < skinnedMeshRenderer.sharedMesh.blendShapeCount; i++)
{
    Debug.Log($"[{i}] {skinnedMeshRenderer.sharedMesh.GetBlendShapeName(i)}");
}
```

### Example Mapping (ReadyPlayerMe / ARKit)

If using ReadyPlayerMe or ARKit blendshapes:

```
A -> jawOpen (index 0)
B -> mouthClosed (index 15)
C -> mouthSmile (index 22)
D -> mouthFunnel (index 18)
E -> mouthLowerDown (index 20)
F -> mouthUpperUp (index 28)
G -> mouthShrugUpper (index 25)
H -> mouthSmile (index 22) // reuse smile
X -> (neutral, no blendshape needed)
```

## Usage

### Basic Connection

```csharp
// Get reference to client
VoiceAgentClient client = FindObjectOfType<VoiceAgentClient>();

// Connect manually (if AutoConnect is false)
await client.ConnectAsync();

// Send text message
await client.SendTextMessage("مرحباً، كيف حالك؟");

// Listen for responses
client.OnResponseReceived += (response) => {
    Debug.Log($"Agent said: {response.text}");
    // Audio and lip-sync are handled automatically
};

// Disconnect
await client.DisconnectAsync();
```

### Sending Audio (Microphone)

```csharp
// Record microphone (example using Unity Microphone)
AudioClip recording = Microphone.Start(null, false, 10, 16000);
yield return new WaitForSeconds(5f); // Record for 5 seconds
Microphone.End(null);

// Convert to WAV bytes
byte[] wavData = AudioClipToWav(recording);

// Send to server
await client.SendAudioMessage(wavData);
```

### Advanced: Custom Viseme Weights

You can manually control visemes:

```csharp
LipSyncController lipSync = GetComponent<LipSyncController>();

// Play viseme timeline manually
List<VisemeFrame> customTimeline = new List<VisemeFrame>
{
    new VisemeFrame { timeMs = 0, id = "A", weight = 1.0f },
    new VisemeFrame { timeMs = 100, id = "B", weight = 0.8f },
    new VisemeFrame { timeMs = 200, id = "X", weight = 1.0f }
};

lipSync.PlayVisemeTimeline(customTimeline, audioSource);
```

## Performance Tips

1. **Reduce Network Latency**:
   - Deploy backend close to client (same region)
   - Use WebSocket keep-alive (client sends ping every 30s)

2. **Smooth Lip-Sync**:
   - Adjust `smoothingSpeed` in LipSyncController (default 10f)
   - Increase `maxBlendshapeWeight` for more exaggerated mouth movement

3. **Audio Sync**:
   - The system uses `AudioSource.time` for precise sync
   - Ensure audio sample rate matches (16kHz recommended)

4. **Memory**:
   - Audio clips are created dynamically and destroyed after playback
   - Large conversations: implement AudioClip pooling

## Troubleshooting

### "WebSocket connection failed"
- Check server URL (must start with `ws://` or `wss://`)
- Verify FastAPI server is running
- Check firewall/network settings

### "No lip-sync animation"
- Verify Rhubarb is installed on backend (`tools/rhubarb`)
- Check server logs for lip-sync generation errors
- Verify blendshape indices are correct
- Test with `lipSync.TestViseme("A", 1.0f)` to check mapping

### "Audio not playing"
- Check `AudioSource` is assigned
- Verify audio decoding (backend should send MP3 or WAV)
- Check Unity audio mixer settings

### "Visemes out of sync with audio"
- Ensure backend and Unity agree on audio format
- Check for network lag (high latency adds delay)
- Verify `AudioSource.time` returns correct values

## Backend Configuration

Ensure backend is configured correctly:

```env
# .env
TTS_ENGINE=edge
TTS_VOICE=ar-EG-SalmaNeural
```

And Rhubarb is installed:
```bash
./scripts/download_rhubarb.sh
```

## Examples

See `Unity/Examples/` for complete sample scenes:
- `SimpleConversation.unity` - Basic text-based conversation
- `VoiceConversation.unity` - Microphone input with lip-sync
- `MultiCharacter.unity` - Multiple characters with independent lip-sync

## API Reference

### VoiceAgentClient

**Methods:**
- `Task ConnectAsync()` - Connect to server
- `Task DisconnectAsync()` - Disconnect from server
- `Task SendTextMessage(string text)` - Send text message
- `Task SendAudioMessage(byte[] audioData)` - Send audio (WAV/PCM)

**Events:**
- `OnConnected` - Fired when connected
- `OnDisconnected` - Fired when disconnected
- `OnTranscriptionReceived(TranscriptionData)` - User speech transcribed
- `OnResponseReceived(ResponseData)` - Agent response received
- `OnError(string)` - Error occurred

### LipSyncController

**Methods:**
- `void PlayVisemeTimeline(List<VisemeFrame>, AudioSource)` - Play viseme animation
- `void Stop()` - Stop current animation
- `void TestViseme(string id, float weight)` - Test single viseme

**Properties:**
- `float smoothingSpeed` - Interpolation speed (default 10)
- `float maxBlendshapeWeight` - Max weight multiplier (default 100)
- `bool isPlaying` - Whether animation is playing

## License

Same as main project (MIT)
