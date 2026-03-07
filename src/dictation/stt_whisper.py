"""Speech-to-text engine using faster-whisper."""
from __future__ import annotations

import logging
import time

import numpy as np
from faster_whisper import WhisperModel

from dictation.stt import STTResult

logger = logging.getLogger(__name__)

# Only re-transcribe after this many new seconds of audio accumulate
_RETRANSCRIBE_SECONDS = 2
_SAMPLE_RATE = 16000
_BYTES_PER_SECOND = _SAMPLE_RATE * 2  # 16-bit mono
_RETRANSCRIBE_BYTES = _RETRANSCRIBE_SECONDS * _BYTES_PER_SECOND


class WhisperSTTEngine:
    """Wraps faster-whisper for speech-to-text.

    Accumulates audio and transcribes periodically since Whisper
    does not support true streaming. Partial results are emitted
    every few seconds; the final result covers the full utterance.
    """

    def __init__(
        self,
        model_size: str = "tiny",
        sample_rate: int = _SAMPLE_RATE,
    ):
        self._model = WhisperModel(model_size, compute_type="int8")
        self.sample_rate = sample_rate
        self._buffer = bytearray()
        self._last_transcribe_len = 0
        self._last_text = ""

    def _transcribe(self, audio_bytes: bytes) -> str:
        audio = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        segments, info = self._model.transcribe(
            audio,
            language="en",
            vad_filter=True,
        )
        text = " ".join(s.text.strip() for s in segments)
        logger.debug("Whisper transcribed %d bytes -> %r", len(audio_bytes), text)
        return text

    def process_audio(self, data: bytes) -> STTResult:
        """Process an audio chunk. Returns partial result periodically."""
        self._buffer.extend(data)
        new_audio = len(self._buffer) - self._last_transcribe_len
        if new_audio >= _RETRANSCRIBE_BYTES:
            self._last_text = self._transcribe(bytes(self._buffer))
            self._last_transcribe_len = len(self._buffer)
            return STTResult(text=self._last_text, is_final=False)
        return STTResult(text="", is_final=False)

    def finalize(self) -> STTResult:
        """Transcribe all accumulated audio and return final result."""
        if self._buffer:
            text = self._transcribe(bytes(self._buffer))
            self._buffer.clear()
            self._last_transcribe_len = 0
            self._last_text = ""
            return STTResult(text=text, is_final=True)
        return STTResult(text="", is_final=True)

    def reset(self) -> None:
        """Reset for a new utterance."""
        self._buffer.clear()
        self._last_transcribe_len = 0
        self._last_text = ""
