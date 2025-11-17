"""Example WebSocket client for real-time voice conversation."""

import asyncio
import base64
import json
from pathlib import Path

import websockets


async def test_websocket_conversation():
    """Test WebSocket conversation endpoint."""
    uri = "ws://localhost:8000/api/v1/ws/conversation"

    async with websockets.connect(uri) as websocket:
        print("Connected to voice agent")

        # Test with text input
        print("\nSending text message...")
        await websocket.send(json.dumps({
            "type": "text",
            "data": "ما هي أحدث المعلومات المتوفرة؟"
        }))

        # Receive response
        response = await websocket.recv()
        response_data = json.loads(response)

        if response_data["type"] == "response":
            data = response_data["data"]
            print(f"\nResponse: {data['text']}")
            print(f"Processing times: {data['processing_times']}")

            # Save audio response
            if "audio" in data:
                audio_bytes = base64.b64decode(data["audio"])
                output_path = Path("output_response.mp3")
                output_path.write_bytes(audio_bytes)
                print(f"\nAudio saved to {output_path}")

        # Test with audio file (if available)
        audio_file = Path("test_audio.wav")
        if audio_file.exists():
            print(f"\nSending audio file: {audio_file}")
            audio_data = audio_file.read_bytes()
            audio_b64 = base64.b64encode(audio_data).decode('utf-8')

            await websocket.send(json.dumps({
                "type": "audio",
                "data": audio_b64
            }))

            # Receive transcription
            trans_response = await websocket.recv()
            trans_data = json.loads(trans_response)
            if trans_data["type"] == "transcription":
                print(f"Transcription: {trans_data['data']['text']}")

            # Receive AI response
            ai_response = await websocket.recv()
            ai_data = json.loads(ai_response)
            if ai_data["type"] == "response":
                print(f"AI Response: {ai_data['data']['text']}")
                print(f"Total processing: {ai_data['data']['processing_times']['total_ms']:.2f}ms")


if __name__ == "__main__":
    asyncio.run(test_websocket_conversation())
