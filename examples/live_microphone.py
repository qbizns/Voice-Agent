"""Example live microphone client with real-time conversation."""

import asyncio
import base64
import json
import sys
from pathlib import Path

import websockets

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.audio import AudioRecorder, VoiceActivityDetector


async def live_conversation():
    """Run live conversation with microphone input."""
    uri = "ws://localhost:8000/api/v1/ws/conversation"

    # Initialize audio recorder
    recorder = AudioRecorder(sample_rate=16000, channels=1, chunk_size=4096)

    # Initialize VAD
    vad = VoiceActivityDetector(
        sample_rate=16000,
        frame_duration_ms=30,
        padding_duration_ms=300,
        energy_threshold=0.01
    )

    print("Connecting to voice agent...")

    try:
        async with websockets.connect(uri) as websocket:
            print("Connected! Speak into your microphone...")
            print("Press Ctrl+C to stop\n")

            recorder.start()

            try:
                while True:
                    # Read audio chunk
                    chunk = recorder.read_chunk()
                    if not chunk:
                        await asyncio.sleep(0.01)
                        continue

                    # Process with VAD
                    is_speaking, utterance = vad.process_frame(chunk)

                    if utterance:
                        print("Speech detected, processing...")

                        # Encode audio
                        audio_b64 = base64.b64encode(utterance).decode('utf-8')

                        # Send to server
                        await websocket.send(json.dumps({
                            "type": "audio",
                            "data": audio_b64
                        }))

                        # Receive transcription
                        trans_msg = await websocket.recv()
                        trans_data = json.loads(trans_msg)

                        if trans_data["type"] == "transcription":
                            text = trans_data["data"]["text"]
                            print(f"\nYou said: {text}")

                        # Receive AI response
                        response_msg = await websocket.recv()
                        response_data = json.loads(response_msg)

                        if response_data["type"] == "response":
                            data = response_data["data"]
                            print(f"Agent: {data['text']}")

                            # Save and play audio response
                            audio_bytes = base64.b64decode(data["audio"])
                            response_file = Path("temp_response.mp3")
                            response_file.write_bytes(audio_bytes)

                            # Play audio (platform-specific)
                            try:
                                import subprocess
                                # Try different audio players
                                for player in ["mpg123", "afplay", "ffplay"]:
                                    try:
                                        subprocess.run(
                                            [player, str(response_file)],
                                            stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL,
                                            check=True
                                        )
                                        break
                                    except (subprocess.CalledProcessError, FileNotFoundError):
                                        continue
                            except Exception as e:
                                print(f"Could not play audio: {e}")

                            times = data["processing_times"]
                            print(f"Processing: {times['total_ms']:.0f}ms\n")

                        # Reset VAD
                        vad.reset()

                    await asyncio.sleep(0.01)

            except KeyboardInterrupt:
                print("\nStopping...")

    finally:
        recorder.close()
        print("Disconnected")


if __name__ == "__main__":
    print("Live Microphone Voice Agent")
    print("=" * 50)
    asyncio.run(live_conversation())
