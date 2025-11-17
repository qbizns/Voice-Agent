"""Audio utilities for recording and processing."""

import asyncio
import wave
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger


class AudioRecorder:
    """Audio recorder for capturing microphone input."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 4096,
        format_type: str = "int16"
    ):
        """Initialize audio recorder.

        Args:
            sample_rate: Sample rate in Hz
            channels: Number of audio channels
            chunk_size: Size of audio chunks
            format_type: Audio format (int16, float32)
        """
        try:
            import pyaudio

            self.pyaudio = pyaudio.PyAudio()
            self.sample_rate = sample_rate
            self.channels = channels
            self.chunk_size = chunk_size

            # Set format
            if format_type == "int16":
                self.format = pyaudio.paInt16
                self.dtype = np.int16
            elif format_type == "float32":
                self.format = pyaudio.paFloat32
                self.dtype = np.float32
            else:
                raise ValueError(f"Unsupported format: {format_type}")

            self.stream: Optional[any] = None
            self.is_recording = False

            logger.info("Audio recorder initialized")

        except ImportError:
            raise ImportError("PyAudio not installed. Install with: pip install pyaudio")

    def start(self) -> None:
        """Start recording."""
        if self.stream is not None:
            logger.warning("Recording already started")
            return

        self.stream = self.pyaudio.open(
            format=self.format,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )

        self.is_recording = True
        logger.info("Recording started")

    def stop(self) -> None:
        """Stop recording."""
        if self.stream is None:
            return

        self.is_recording = False
        self.stream.stop_stream()
        self.stream.close()
        self.stream = None

        logger.info("Recording stopped")

    def read_chunk(self) -> Optional[bytes]:
        """Read one audio chunk.

        Returns:
            Audio chunk in bytes, or None if not recording
        """
        if not self.is_recording or self.stream is None:
            return None

        try:
            data = self.stream.read(self.chunk_size, exception_on_overflow=False)
            return data
        except Exception as e:
            logger.error(f"Error reading audio chunk: {e}")
            return None

    async def record_async(self, duration: float) -> bytes:
        """Record audio asynchronously for a specific duration.

        Args:
            duration: Duration in seconds

        Returns:
            Recorded audio data
        """
        frames = []
        chunks_needed = int(self.sample_rate / self.chunk_size * duration)

        self.start()

        for _ in range(chunks_needed):
            chunk = self.read_chunk()
            if chunk:
                frames.append(chunk)
            await asyncio.sleep(0.001)  # Small delay to allow other tasks

        self.stop()

        return b"".join(frames)

    def save_wav(self, audio_data: bytes, filename: str | Path) -> None:
        """Save audio data to WAV file.

        Args:
            audio_data: Audio data in bytes
            filename: Output filename
        """
        filename = Path(filename)
        filename.parent.mkdir(parents=True, exist_ok=True)

        with wave.open(str(filename), "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.pyaudio.get_sample_size(self.format))
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data)

        logger.info(f"Audio saved to {filename}")

    def close(self) -> None:
        """Clean up resources."""
        self.stop()
        self.pyaudio.terminate()


class VoiceActivityDetector:
    """Simple voice activity detection based on energy threshold."""

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30,
        padding_duration_ms: int = 300,
        energy_threshold: float = 0.01
    ):
        """Initialize VAD.

        Args:
            sample_rate: Sample rate in Hz
            frame_duration_ms: Duration of each frame in milliseconds
            padding_duration_ms: Padding duration for speech boundaries
            energy_threshold: Energy threshold for speech detection
        """
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.padding_duration_ms = padding_duration_ms
        self.energy_threshold = energy_threshold

        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        self.padding_frames = int(padding_duration_ms / frame_duration_ms)

        self.triggered = False
        self.voiced_frames = []
        self.ring_buffer = []

    def is_speech(self, audio_frame: bytes) -> bool:
        """Detect if audio frame contains speech.

        Args:
            audio_frame: Audio frame data

        Returns:
            True if speech detected, False otherwise
        """
        # Convert to numpy array
        audio_np = np.frombuffer(audio_frame, dtype=np.int16).astype(np.float32) / 32768.0

        # Calculate energy
        energy = np.sum(audio_np ** 2) / len(audio_np)

        return energy > self.energy_threshold

    def process_frame(self, audio_frame: bytes) -> tuple[bool, Optional[bytes]]:
        """Process audio frame and detect voice activity.

        Args:
            audio_frame: Audio frame data

        Returns:
            Tuple of (is_speaking, complete_utterance_if_done)
        """
        is_speech = self.is_speech(audio_frame)

        if not self.triggered:
            self.ring_buffer.append((audio_frame, is_speech))
            if len(self.ring_buffer) > self.padding_frames:
                self.ring_buffer.pop(0)

            # Check if enough voiced frames in ring buffer
            num_voiced = sum(1 for _, voiced in self.ring_buffer if voiced)
            if num_voiced > 0.9 * len(self.ring_buffer):
                self.triggered = True
                # Add ring buffer to voiced frames
                self.voiced_frames.extend([f for f, _ in self.ring_buffer])
                self.ring_buffer.clear()

            return False, None

        else:
            # Already triggered
            self.voiced_frames.append(audio_frame)

            self.ring_buffer.append((audio_frame, is_speech))
            if len(self.ring_buffer) > self.padding_frames:
                self.ring_buffer.pop(0)

            # Check if speech has ended
            num_unvoiced = sum(1 for _, voiced in self.ring_buffer if not voiced)
            if num_unvoiced > 0.9 * len(self.ring_buffer):
                # Speech ended
                self.triggered = False
                utterance = b"".join(self.voiced_frames)
                self.voiced_frames.clear()
                self.ring_buffer.clear()
                return False, utterance

            return True, None

    def reset(self) -> None:
        """Reset VAD state."""
        self.triggered = False
        self.voiced_frames.clear()
        self.ring_buffer.clear()
