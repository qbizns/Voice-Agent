"""Lip-sync service using Rhubarb Lip Sync for viseme generation."""

import asyncio
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from app.core.config import get_settings


class VisemeFrame:
    """Single viseme keyframe with timestamp and intensity."""

    def __init__(self, time_ms: float, viseme_id: str, weight: float = 1.0):
        """Initialize viseme frame.

        Args:
            time_ms: Timestamp in milliseconds from start of audio
            viseme_id: Viseme identifier (A, B, C, D, E, F, G, H, X)
            weight: Intensity/weight 0.0-1.0
        """
        self.time_ms = time_ms
        self.viseme_id = viseme_id
        self.weight = weight

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "time_ms": self.time_ms,
            "id": self.viseme_id,
            "weight": self.weight
        }

    def __repr__(self) -> str:
        return f"VisemeFrame(time_ms={self.time_ms}, id={self.viseme_id}, weight={self.weight})"


class LipSyncService:
    """Service for generating lip-sync viseme timelines from audio."""

    def __init__(self, rhubarb_path: Optional[str] = None):
        """Initialize lip-sync service.

        Args:
            rhubarb_path: Path to Rhubarb executable (defaults to tools/rhubarb)
        """
        settings = get_settings()

        # Default rhubarb path
        if rhubarb_path is None:
            rhubarb_path = "tools/rhubarb"

        self.rhubarb_path = Path(rhubarb_path)

        if not self.rhubarb_path.exists():
            logger.warning(
                f"Rhubarb executable not found at {self.rhubarb_path}. "
                f"Lip-sync will be disabled. Download from: "
                f"https://github.com/DanielSWolf/rhubarb-lip-sync/releases"
            )
            self.enabled = False
        else:
            self.enabled = True
            logger.info(f"Lip-sync service initialized with Rhubarb at {self.rhubarb_path}")

    async def generate_visemes(
        self,
        audio_data: bytes,
        text: Optional[str] = None,
        audio_format: str = "mp3"
    ) -> tuple[list[VisemeFrame], float]:
        """Generate viseme timeline from audio.

        Args:
            audio_data: Audio data in bytes
            text: Optional transcript text (improves accuracy)
            audio_format: Audio format (mp3, wav, ogg)

        Returns:
            Tuple of (viseme_frames, processing_time_ms)
        """
        if not self.enabled:
            logger.warning("Lip-sync service disabled, returning empty viseme timeline")
            return [], 0.0

        start_time = time.perf_counter()

        # Create temporary files
        with tempfile.NamedTemporaryFile(
            suffix=f".{audio_format}",
            delete=False
        ) as audio_file:
            audio_file.write(audio_data)
            audio_path = Path(audio_file.name)

        try:
            # Run Rhubarb
            visemes = await self._run_rhubarb(audio_path, text)

            processing_time = (time.perf_counter() - start_time) * 1000
            logger.debug(f"Generated {len(visemes)} viseme frames in {processing_time:.2f}ms")

            return visemes, processing_time

        finally:
            # Cleanup
            if audio_path.exists():
                audio_path.unlink()

    async def _run_rhubarb(
        self,
        audio_path: Path,
        text: Optional[str] = None
    ) -> list[VisemeFrame]:
        """Run Rhubarb lip-sync tool.

        Args:
            audio_path: Path to audio file
            text: Optional dialog text

        Returns:
            List of viseme frames
        """
        # Build Rhubarb command
        cmd = [
            str(self.rhubarb_path),
            str(audio_path),
            "--exportFormat", "json",
            "--machineReadable"
        ]

        # Add dialog text if provided (improves accuracy)
        if text:
            # Create temporary dialog file
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.txt',
                delete=False,
                encoding='utf-8'
            ) as dialog_file:
                dialog_file.write(text)
                dialog_path = Path(dialog_file.name)

            cmd.extend(["--dialogFile", str(dialog_path)])
        else:
            dialog_path = None

        try:
            # Run Rhubarb asynchronously
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._run_rhubarb_sync,
                cmd
            )

            # Parse result
            visemes = self._parse_rhubarb_output(result)

            return visemes

        finally:
            # Cleanup dialog file
            if dialog_path and dialog_path.exists():
                dialog_path.unlink()

    def _run_rhubarb_sync(self, cmd: list[str]) -> str:
        """Run Rhubarb synchronously.

        Args:
            cmd: Command list

        Returns:
            JSON output from Rhubarb
        """
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30  # 30 second timeout
            )
            return result.stdout

        except subprocess.CalledProcessError as e:
            logger.error(f"Rhubarb failed: {e.stderr}")
            raise RuntimeError(f"Rhubarb lip-sync failed: {e.stderr}")
        except subprocess.TimeoutExpired:
            logger.error("Rhubarb timed out")
            raise RuntimeError("Rhubarb lip-sync timed out")

    def _parse_rhubarb_output(self, json_output: str) -> list[VisemeFrame]:
        """Parse Rhubarb JSON output into viseme frames.

        Args:
            json_output: JSON string from Rhubarb

        Returns:
            List of viseme frames
        """
        try:
            data = json.loads(json_output)

            # Rhubarb output format:
            # {
            #   "metadata": { ... },
            #   "mouthCues": [
            #     { "start": 0.00, "end": 0.37, "value": "X" },
            #     { "start": 0.37, "end": 0.51, "value": "B" },
            #     ...
            #   ]
            # }

            mouth_cues = data.get("mouthCues", [])
            visemes = []

            for cue in mouth_cues:
                start_ms = cue["start"] * 1000  # Convert seconds to milliseconds
                viseme_id = cue["value"]

                # Add keyframe at start of cue
                visemes.append(VisemeFrame(
                    time_ms=start_ms,
                    viseme_id=viseme_id,
                    weight=1.0
                ))

            return visemes

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse Rhubarb output: {e}")
            return []

    def get_duration_ms(self, visemes: list[VisemeFrame]) -> float:
        """Get total duration of viseme timeline.

        Args:
            visemes: List of viseme frames

        Returns:
            Duration in milliseconds
        """
        if not visemes:
            return 0.0

        return max(v.time_ms for v in visemes)
