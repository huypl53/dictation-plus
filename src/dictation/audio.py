"""Audio capture and playback using sounddevice."""
from __future__ import annotations

import queue
from typing import Callable

import numpy as np
import sounddevice as sd


class AudioCapture:
    """Captures audio from the microphone in real-time."""

    def __init__(self, sample_rate: int = 16000, block_size: int = 8000):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.audio_queue: queue.Queue[bytes] = queue.Queue()
        self._stream: sd.RawInputStream | None = None

    def _callback(self, indata, frames, time, status):
        if status:
            import sys
            print(status, file=sys.stderr)
        self.audio_queue.put(bytes(indata))

    def start(self) -> None:
        """Start capturing audio."""
        self._stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=self.block_size,
            dtype="int16",
            channels=1,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> None:
        """Stop capturing audio."""
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def read(self, timeout: float = 1.0) -> bytes | None:
        """Read the next audio chunk from the queue."""
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    @property
    def is_active(self) -> bool:
        return self._stream is not None and self._stream.active


class AudioPlayback:
    """Plays audio through the default speakers."""

    def play_raw(self, data: bytes, sample_rate: int = 22050) -> None:
        """Play raw 16-bit PCM audio."""
        audio = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
        sd.play(audio, samplerate=sample_rate)
        sd.wait()
