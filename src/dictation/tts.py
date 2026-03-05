"""Text-to-speech engine using Piper."""
from __future__ import annotations

import io
import wave
from pathlib import Path

from piper import PiperVoice


class TTSEngine:
    """Wraps Piper for text-to-speech synthesis."""

    def __init__(self, model_path: str | Path):
        self._voice = PiperVoice.load(str(model_path))

    def synthesize(self, text: str) -> bytes:
        """Synthesize text to WAV bytes in memory."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            self._voice.synthesize_wav(text, wav_file)
        return buf.getvalue()

    def synthesize_to_file(self, text: str, path: Path) -> None:
        """Synthesize text and save to a WAV file."""
        with wave.open(str(path), "wb") as wav_file:
            self._voice.synthesize_wav(text, wav_file)

    def synthesize_stream(self, text: str):
        """Yield audio chunks for streaming playback."""
        for chunk in self._voice.synthesize(text):
            yield chunk
