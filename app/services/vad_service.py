"""Voice Activity Detection (VAD) service.

Provides automatic speech detection to determine when user has finished speaking.
Uses Silero VAD for lightweight, accurate voice detection.
"""

import torch
import numpy as np
from typing import Optional, Tuple
from loguru import logger


class VADService:
    """Voice Activity Detection using Silero VAD."""

    def __init__(
        self,
        threshold: float = 0.5,
        sampling_rate: int = 16000,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 800,
        window_size_samples: int = 512,
    ):
        """Initialize VAD service.

        Args:
            threshold: Voice probability threshold (0.0-1.0)
            sampling_rate: Audio sample rate in Hz
            min_speech_duration_ms: Minimum speech duration to trigger detection
            min_silence_duration_ms: Silence duration to end speech
            window_size_samples: VAD analysis window size
        """
        self.threshold = threshold
        self.sampling_rate = sampling_rate
        self.min_speech_duration_ms = min_speech_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms
        self.window_size_samples = window_size_samples

        # State tracking
        self.is_speech = False
        self.speech_start_sample = 0
        self.silence_start_sample = 0
        self.total_samples_processed = 0

        # Try to load Silero VAD model
        self.model = None
        self.enabled = False
        self._load_model()

        logger.info(f"VAD service initialized (enabled={self.enabled})")

    def _load_model(self):
        """Load Silero VAD model."""
        try:
            # Load Silero VAD from torch hub
            self.model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=False,
            )

            # Extract utility functions
            (get_speech_timestamps, _, read_audio, *_) = utils

            self.get_speech_timestamps = get_speech_timestamps
            self.enabled = True

            logger.info("Silero VAD model loaded successfully")

        except Exception as e:
            logger.warning(f"Failed to load Silero VAD: {e}")
            logger.warning("VAD will be disabled. Install with: pip install torch torchaudio")
            self.enabled = False

    def process_chunk(
        self, audio_chunk: np.ndarray
    ) -> Tuple[bool, float]:
        """Process audio chunk and return speech probability.

        Args:
            audio_chunk: Audio data as numpy array (float32, range -1.0 to 1.0)

        Returns:
            Tuple of (is_speech: bool, confidence: float)
        """
        if not self.enabled or self.model is None:
            return False, 0.0

        try:
            # Convert to torch tensor
            if isinstance(audio_chunk, np.ndarray):
                audio_tensor = torch.from_numpy(audio_chunk).float()
            else:
                audio_tensor = audio_chunk

            # Ensure correct shape (1D)
            if audio_tensor.dim() > 1:
                audio_tensor = audio_tensor.squeeze()

            # Get speech probability
            with torch.no_grad():
                speech_prob = self.model(audio_tensor, self.sampling_rate).item()

            is_speech = speech_prob >= self.threshold

            return is_speech, speech_prob

        except Exception as e:
            logger.error(f"Error processing VAD chunk: {e}")
            return False, 0.0

    def detect_speech_segments(
        self, audio_data: np.ndarray
    ) -> list[dict]:
        """Detect all speech segments in audio data.

        Args:
            audio_data: Full audio array (float32, mono)

        Returns:
            List of speech segments with start/end timestamps
            [{"start": 0.5, "end": 2.3, "confidence": 0.95}, ...]
        """
        if not self.enabled or self.model is None:
            return []

        try:
            # Convert to torch tensor
            audio_tensor = torch.from_numpy(audio_data).float()

            # Get speech timestamps
            speech_timestamps = self.get_speech_timestamps(
                audio_tensor,
                self.model,
                sampling_rate=self.sampling_rate,
                threshold=self.threshold,
                min_speech_duration_ms=self.min_speech_duration_ms,
                min_silence_duration_ms=self.min_silence_duration_ms,
            )

            # Convert to seconds
            segments = []
            for ts in speech_timestamps:
                segments.append({
                    "start": ts["start"] / self.sampling_rate,
                    "end": ts["end"] / self.sampling_rate,
                    "confidence": 1.0,  # Silero doesn't provide per-segment confidence
                })

            return segments

        except Exception as e:
            logger.error(f"Error detecting speech segments: {e}")
            return []

    def reset(self):
        """Reset VAD state."""
        self.is_speech = False
        self.speech_start_sample = 0
        self.silence_start_sample = 0
        self.total_samples_processed = 0


class StreamingVAD:
    """Streaming VAD for real-time speech detection."""

    def __init__(
        self,
        vad_service: VADService,
        silence_duration_ms: int = 800,
        speech_pad_ms: int = 300,
    ):
        """Initialize streaming VAD.

        Args:
            vad_service: VAD service instance
            silence_duration_ms: Silence duration to trigger end-of-speech
            speech_pad_ms: Padding to add before/after speech
        """
        self.vad = vad_service
        self.silence_duration_ms = silence_duration_ms
        self.speech_pad_ms = speech_pad_ms

        # State
        self.is_speaking = False
        self.silence_samples = 0
        self.speech_samples = 0
        self.silence_threshold_samples = int(
            (silence_duration_ms / 1000.0) * vad_service.sampling_rate
        )

        logger.info(f"Streaming VAD initialized (silence_threshold={silence_duration_ms}ms)")

    def process_audio(self, audio_chunk: np.ndarray) -> dict:
        """Process audio chunk and return speech state.

        Args:
            audio_chunk: Audio chunk (float32, mono)

        Returns:
            {
                "is_speaking": bool,
                "speech_ended": bool,  # True when silence threshold reached
                "confidence": float,
                "silence_duration_ms": float
            }
        """
        if not self.vad.enabled:
            # If VAD disabled, always return as not speaking
            return {
                "is_speaking": False,
                "speech_ended": False,
                "confidence": 0.0,
                "silence_duration_ms": 0.0,
            }

        # Get speech probability
        is_speech, confidence = self.vad.process_chunk(audio_chunk)

        speech_ended = False

        if is_speech:
            # Speech detected
            self.speech_samples += len(audio_chunk)
            self.silence_samples = 0
            self.is_speaking = True

        else:
            # Silence detected
            if self.is_speaking:
                self.silence_samples += len(audio_chunk)

                # Check if silence threshold reached
                if self.silence_samples >= self.silence_threshold_samples:
                    speech_ended = True
                    self.is_speaking = False
                    self.speech_samples = 0
                    self.silence_samples = 0

        silence_duration_ms = (
            self.silence_samples / self.vad.sampling_rate * 1000.0
        )

        return {
            "is_speaking": self.is_speaking,
            "speech_ended": speech_ended,
            "confidence": confidence,
            "silence_duration_ms": silence_duration_ms,
        }

    def reset(self):
        """Reset streaming VAD state."""
        self.is_speaking = False
        self.silence_samples = 0
        self.speech_samples = 0
