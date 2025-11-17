"""Example REST API client for voice agent."""

import httpx
from pathlib import Path


def test_health():
    """Test health endpoint."""
    response = httpx.get("http://localhost:8000/api/v1/health")
    print("Health check:", response.json())


def test_chat():
    """Test chat endpoint."""
    response = httpx.post(
        "http://localhost:8000/api/v1/chat",
        json={
            "message": "ما هو الطقس اليوم؟",
            "use_knowledge_base": True
        }
    )
    data = response.json()
    print(f"\nChat Response: {data['response']}")
    print(f"Processing time: {data['processing_time_ms']:.2f}ms")
    if data.get("sources"):
        print(f"Sources: {data['sources']}")


def test_transcribe():
    """Test transcription endpoint."""
    audio_file = Path("test_audio.wav")
    if not audio_file.exists():
        print(f"Audio file not found: {audio_file}")
        return

    with open(audio_file, "rb") as f:
        response = httpx.post(
            "http://localhost:8000/api/v1/transcribe",
            files={"audio": f}
        )

    data = response.json()
    print(f"\nTranscription: {data['text']}")
    print(f"Confidence: {data.get('confidence', 'N/A')}")
    print(f"Processing time: {data['processing_time_ms']:.2f}ms")


def test_synthesize():
    """Test synthesis endpoint."""
    response = httpx.post(
        "http://localhost:8000/api/v1/synthesize",
        params={"text": "مرحباً، كيف يمكنني مساعدتك اليوم؟"}
    )

    if response.status_code == 200:
        output_file = Path("output.mp3")
        output_file.write_bytes(response.content)
        print(f"\nSynthesis successful. Audio saved to {output_file}")
        print(f"Processing time: {response.headers.get('X-Processing-Time-Ms')}ms")
    else:
        print(f"Synthesis failed: {response.text}")


if __name__ == "__main__":
    print("Testing Voice Agent API\n")
    print("=" * 50)

    test_health()
    print("\n" + "=" * 50)

    test_chat()
    print("\n" + "=" * 50)

    test_synthesize()
    print("\n" + "=" * 50)

    # Uncomment if you have test audio file
    # test_transcribe()
