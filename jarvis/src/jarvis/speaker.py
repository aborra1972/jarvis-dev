"""Speaker verification using Resemblyzer.

Provides voice enrollment and verification to ensure Jarvis only
responds to the authorized speaker. Uses d-vector embeddings for
speaker identification.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
import wave
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("jarvis.speaker")

# Default enrollment file path (relative to project root)
DEFAULT_ENROLLMENT_FILE = "speaker_embedding.json"
DEFAULT_THRESHOLD = 0.75  # Minimum cosine similarity to accept
DEFAULT_ENROLLMENT_SECONDS = 10  # Seconds of audio for enrollment
DEFAULT_SAMPLE_RATE = 16000


class SpeakerVerifier:
    """Handles speaker enrollment and verification."""

    def __init__(
        self,
        enrollment_file: str | Path = DEFAULT_ENROLLMENT_FILE,
        threshold: float = DEFAULT_THRESHOLD,
    ):
        self.enrollment_file = Path(enrollment_file)
        self.threshold = threshold
        self._encoder = None
        self._enrolled_embedding: Optional[np.ndarray] = None

    def _load_encoder(self):
        """Lazy-load the Resemblyzer encoder."""
        if self._encoder is None:
            from resemblyzer import VoiceEncoder
            self._encoder = VoiceEncoder()
        return self._encoder

    def is_enrolled(self) -> bool:
        """Check if a speaker is enrolled."""
        return self.enrollment_file.exists()

    def enroll_from_file(self, audio_path: str | Path) -> bool:
        """Enroll speaker from a WAV audio file.

        Args:
            audio_path: Path to a WAV file with the speaker's voice.

        Returns:
            True if enrollment succeeded, False otherwise.
        """
        from resemblyzer import preprocess_wav

        try:
            audio_path = Path(audio_path)
            if not audio_path.exists():
                logger.error("Audio file not found: %s", audio_path)
                return False

            # Preprocess and extract embedding
            wav = preprocess_wav(audio_path)
            if len(wav) < DEFAULT_SAMPLE_RATE * 2:
                logger.error("Audio too short for enrollment (need 2+ seconds)")
                return False

            encoder = self._load_encoder()
            embedding = encoder.embed_utterance(wav)

            # Save embedding
            self._save_embedding(embedding)
            self._enrolled_embedding = embedding

            logger.info("Speaker enrolled successfully from %s", audio_path)
            return True

        except Exception as exc:
            logger.error("Enrollment failed: %s", exc)
            return False

    def enroll_from_mic(self, duration: float = DEFAULT_ENROLLMENT_SECONDS) -> bool:
        """Enroll speaker by recording from microphone.

        Args:
            duration: Seconds to record.

        Returns:
            True if enrollment succeeded, False otherwise.
        """
        from resemblyzer import preprocess_wav

        try:
            logger.info("Recording enrollment audio for %.1f seconds...", duration)

            # Record audio
            import sounddevice as sd
            audio = sd.rec(
                int(duration * DEFAULT_SAMPLE_RATE),
                samplerate=DEFAULT_SAMPLE_RATE,
                channels=1,
                dtype="float32",
            )
            sd.wait()

            # Flatten to 1D
            audio = audio.flatten()

            # Check audio quality
            rms = np.sqrt(np.mean(audio**2))
            if rms < 0.01:
                logger.error("Audio too quiet for enrollment (RMS: %.4f)", rms)
                return False

            # Preprocess and extract embedding
            wav = preprocess_wav(audio, source_sr=DEFAULT_SAMPLE_RATE)
            encoder = self._load_encoder()
            embedding = encoder.embed_utterance(wav)

            # Save embedding
            self._save_embedding(embedding)
            self._enrolled_embedding = embedding

            logger.info("Speaker enrolled successfully from microphone")
            return True

        except Exception as exc:
            logger.error("Microphone enrollment failed: %s", exc)
            return False

    def verify(self, audio: np.ndarray) -> tuple[bool, float]:
        """Verify if audio matches the enrolled speaker.

        Args:
            audio: Audio array (float32, 16kHz).

        Returns:
            Tuple of (is_match, similarity_score).
        """
        from resemblyzer import preprocess_wav

        try:
            # Load enrolled embedding if not cached
            if self._enrolled_embedding is None:
                self._enrolled_embedding = self._load_embedding()

            if self._enrolled_embedding is None:
                # No enrollment → allow everyone (backward compatible)
                logger.warning("No speaker enrolled, allowing all voices")
                return True, 1.0

            # Preprocess audio
            wav = preprocess_wav(audio, source_sr=DEFAULT_SAMPLE_RATE)

            if len(wav) < DEFAULT_SAMPLE_RATE:
                # Too short for reliable verification
                logger.warning("Audio too short for verification (%.1fs)", len(wav) / DEFAULT_SAMPLE_RATE)
                return True, 0.5

            # Extract embedding
            encoder = self._load_encoder()
            embedding = encoder.embed_utterance(wav)

            # Cosine similarity
            similarity = np.dot(embedding, self._enrolled_embedding) / (
                np.linalg.norm(embedding) * np.linalg.norm(self._enrolled_embedding)
            )

            is_match = similarity >= self.threshold
            logger.info("Speaker verification: similarity=%.3f, match=%s", similarity, is_match)

            return is_match, float(similarity)

        except Exception as exc:
            logger.error("Verification failed: %s", exc)
            # Fail open (allow) on error
            return True, 0.0

    def verify_file(self, audio_path: str | Path) -> tuple[bool, float]:
        """Verify audio from a file.

        Args:
            audio_path: Path to a WAV file.

        Returns:
            Tuple of (is_match, similarity_score).
        """
        import soundfile as sf

        try:
            audio, sr = sf.read(audio_path, dtype="float32")

            # Resample if needed
            if sr != DEFAULT_SAMPLE_RATE:
                import librosa
                audio = librosa.resample(audio, orig_sr=sr, target_sr=DEFAULT_SAMPLE_RATE)

            # Ensure mono
            if audio.ndim > 1:
                audio = audio.mean(axis=1)

            return self.verify(audio)

        except Exception as exc:
            logger.error("File verification failed: %s", exc)
            return True, 0.0

    def _save_embedding(self, embedding: np.ndarray):
        """Save embedding to JSON file."""
        data = {
            "embedding": embedding.tolist(),
            "created_at": time.time(),
            "threshold": self.threshold,
        }

        self.enrollment_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.enrollment_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.info("Speaker embedding saved to %s", self.enrollment_file)

    def _load_embedding(self) -> Optional[np.ndarray]:
        """Load embedding from JSON file."""
        try:
            if not self.enrollment_file.exists():
                return None

            with open(self.enrollment_file) as f:
                data = json.load(f)

            embedding = np.array(data["embedding"], dtype=np.float32)

            # Update threshold from file if present
            if "threshold" in data:
                self.threshold = data["threshold"]

            logger.info("Speaker embedding loaded from %s", self.enrollment_file)
            return embedding

        except Exception as exc:
            logger.error("Failed to load embedding: %s", exc)
            return None

    def get_info(self) -> dict:
        """Get enrollment status and info."""
        if not self.is_enrolled():
            return {"enrolled": False}

        embedding = self._load_embedding()
        return {
            "enrolled": True,
            "file": str(self.enrollment_file),
            "created_at": embedding.get("created_at") if embedding else None,
            "threshold": self.threshold,
        }


# Singleton instance
_verifier: Optional[SpeakerVerifier] = None


def get_verifier(
    enrollment_file: str | Path | None = None,
    threshold: float | None = None,
) -> SpeakerVerifier:
    """Get or create the speaker verifier singleton."""
    global _verifier
    if _verifier is None:
        from jarvis import config

        if enrollment_file is None:
            enrollment_file = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                DEFAULT_ENROLLMENT_FILE,
            )
        if threshold is None:
            threshold = getattr(config, "SPEAKER_THRESHOLD", DEFAULT_THRESHOLD)

        _verifier = SpeakerVerifier(enrollment_file=enrollment_file, threshold=threshold)
    return _verifier
