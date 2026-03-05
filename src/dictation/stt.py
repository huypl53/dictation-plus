"""Speech-to-text engine using Vosk."""
from __future__ import annotations

import json
from dataclasses import dataclass

from vosk import Model, KaldiRecognizer


@dataclass
class STTResult:
    text: str
    is_final: bool


class STTEngine:
    """Wraps Vosk for streaming speech-to-text."""

    def __init__(
        self,
        model_path: str | None = None,
        model_name: str | None = None,
        lang: str | None = None,
        sample_rate: int = 16000,
    ):
        if model_path:
            self._model = Model(model_path=model_path)
        elif model_name:
            self._model = Model(model_name=model_name)
        elif lang:
            self._model = Model(lang=lang)
        else:
            self._model = Model(lang="en-us")

        self.sample_rate = sample_rate
        self._recognizer = KaldiRecognizer(self._model, self.sample_rate)

    def process_audio(self, data: bytes) -> STTResult:
        """Process an audio chunk. Returns partial or final result."""
        if self._recognizer.AcceptWaveform(data):
            result = json.loads(self._recognizer.Result())
            return STTResult(text=result.get("text", ""), is_final=True)
        else:
            partial = json.loads(self._recognizer.PartialResult())
            return STTResult(text=partial.get("partial", ""), is_final=False)

    def finalize(self) -> STTResult:
        """Flush remaining audio and return final result."""
        result = json.loads(self._recognizer.FinalResult())
        return STTResult(text=result.get("text", ""), is_final=True)

    def reset(self) -> None:
        """Reset the recognizer for a new utterance."""
        self._recognizer = KaldiRecognizer(self._model, self.sample_rate)
