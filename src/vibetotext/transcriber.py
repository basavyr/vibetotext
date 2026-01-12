"""Whisper transcription."""

import numpy as np
from typing import Optional
import whisper


class Transcriber:
    """Transcribes audio using local Whisper model."""

    def __init__(self, model_name: str = "base"):
        """
        Initialize transcriber.

        Args:
            model_name: Whisper model size. Options: tiny, base, small, medium, large
                       Bigger = more accurate but slower.
                       'base' is a good balance for real-time use.
        """
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        """Lazy load the model."""
        if self._model is None:
            print(f"Loading Whisper model '{self.model_name}'...")
            self._model = whisper.load_model(self.model_name)
        return self._model

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        """
        Transcribe audio to text.

        Args:
            audio: Audio data as numpy array (float32, mono)
            sample_rate: Sample rate of audio (Whisper expects 16000)

        Returns:
            Transcribed text
        """
        if len(audio) == 0:
            return ""

        # Whisper expects float32 audio normalized to [-1, 1]
        audio = audio.astype(np.float32)

        # Transcribe
        result = self.model.transcribe(
            audio,
            language="en",
            fp16=False,  # Use fp32 for CPU compatibility
        )

        return result["text"].strip()
