# Local Dictation Service — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a lightweight local dictation service with real-time STT (Vosk) and TTS (Piper), system-wide hotkey, and a REST/WebSocket API.

**Architecture:** Python daemon with Vosk for streaming speech-to-text, Piper for text-to-speech, FastAPI for the local API, pynput for global hotkey, and xdotool/wtype for typing into focused windows.

**Tech Stack:** Python 3.11+, vosk, piper-tts, fastapi, uvicorn, sounddevice, pynput, tomli

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/dictation/__init__.py`
- Create: `src/dictation/py.typed`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "dictation"
version = "0.1.0"
description = "Lightweight local dictation service with STT and TTS"
requires-python = ">=3.11"
dependencies = [
    "vosk>=0.3.45",
    "piper-tts>=1.2.0",
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sounddevice>=0.5.0",
    "pynput>=1.7.0",
    "tomli>=2.0.0; python_version < '3.11'",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
]

[project.scripts]
dictation = "dictation.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/dictation"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

**Step 2: Create package files**

`src/dictation/__init__.py`:
```python
"""Lightweight local dictation service."""
```

`src/dictation/py.typed`: empty marker file.

`tests/__init__.py`: empty.

`tests/conftest.py`:
```python
"""Shared test fixtures."""
```

**Step 3: Create virtual environment and install**

Run: `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
Expected: Successful install with all dependencies.

**Step 4: Verify pytest runs**

Run: `source .venv/bin/activate && python -m pytest --co -q`
Expected: "no tests ran" (no test files yet), exit 0 or 5.

**Step 5: Commit**

```bash
git add pyproject.toml src/ tests/
git commit -m "feat: project scaffolding with dependencies"
```

---

### Task 2: Configuration Module

**Files:**
- Create: `src/dictation/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing tests**

`tests/test_config.py`:
```python
"""Tests for configuration loading."""
import pytest
from pathlib import Path
from dictation.config import DictationConfig, load_config, DEFAULT_CONFIG


def test_default_config_values():
    config = DictationConfig()
    assert config.hotkey == "super+d"
    assert config.api_port == 5678
    assert config.stt_model == "vosk-model-small-en-us-0.15"
    assert config.stt_language == "en"
    assert config.tts_voice == "en_US-lessac-medium"
    assert config.models_dir == Path.home() / ".local" / "share" / "dictation" / "models"


def test_load_config_from_toml(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[general]\nhotkey = "ctrl+shift+d"\napi_port = 9999\n'
        '[stt]\nmodel = "vosk-model-en-us-0.22"\n'
        '[tts]\nvoice = "en_US-amy-low"\n'
    )
    config = load_config(config_file)
    assert config.hotkey == "ctrl+shift+d"
    assert config.api_port == 9999
    assert config.stt_model == "vosk-model-en-us-0.22"
    assert config.tts_voice == "en_US-amy-low"


def test_load_config_missing_file_returns_defaults():
    config = load_config(Path("/nonexistent/config.toml"))
    assert config.hotkey == "super+d"


def test_load_config_partial_override(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[general]\napi_port = 7777\n')
    config = load_config(config_file)
    assert config.api_port == 7777
    assert config.hotkey == "super+d"  # default preserved
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dictation.config'`

**Step 3: Write implementation**

`src/dictation/config.py`:
```python
"""Configuration management."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DictationConfig:
    hotkey: str = "super+d"
    api_port: int = 5678
    stt_model: str = "vosk-model-small-en-us-0.15"
    stt_language: str = "en"
    tts_voice: str = "en_US-lessac-medium"
    models_dir: Path = field(
        default_factory=lambda: Path.home() / ".local" / "share" / "dictation" / "models"
    )


DEFAULT_CONFIG = DictationConfig()

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "dictation" / "config.toml"


def load_config(path: Path | None = None) -> DictationConfig:
    """Load config from TOML file, falling back to defaults for missing keys."""
    if path is None:
        path = DEFAULT_CONFIG_PATH

    if not path.exists():
        return DictationConfig()

    with open(path, "rb") as f:
        data = tomllib.load(f)

    general = data.get("general", {})
    stt = data.get("stt", {})
    tts = data.get("tts", {})

    return DictationConfig(
        hotkey=general.get("hotkey", DEFAULT_CONFIG.hotkey),
        api_port=general.get("api_port", DEFAULT_CONFIG.api_port),
        stt_model=stt.get("model", DEFAULT_CONFIG.stt_model),
        stt_language=stt.get("language", DEFAULT_CONFIG.stt_language),
        tts_voice=tts.get("voice", DEFAULT_CONFIG.tts_voice),
        models_dir=Path(general.get("models_dir", str(DEFAULT_CONFIG.models_dir))),
    )
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: All 4 tests PASS.

**Step 5: Commit**

```bash
git add src/dictation/config.py tests/test_config.py
git commit -m "feat: configuration module with TOML loading"
```

---

### Task 3: STT Engine (Vosk Wrapper)

**Files:**
- Create: `src/dictation/stt.py`
- Create: `tests/test_stt.py`

**Step 1: Write the failing tests**

`tests/test_stt.py`:
```python
"""Tests for STT engine."""
import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from dictation.stt import STTEngine, STTResult


def test_stt_result_dataclass():
    result = STTResult(text="hello", is_final=True)
    assert result.text == "hello"
    assert result.is_final is True


def test_stt_result_partial():
    result = STTResult(text="hel", is_final=False)
    assert result.is_final is False


@patch("dictation.stt.Model")
def test_stt_engine_init(mock_model_cls):
    engine = STTEngine(model_path="/fake/model")
    mock_model_cls.assert_called_once_with(model_path="/fake/model")
    assert engine.sample_rate == 16000


@patch("dictation.stt.KaldiRecognizer")
@patch("dictation.stt.Model")
def test_stt_engine_process_audio_partial(mock_model_cls, mock_rec_cls):
    engine = STTEngine(model_path="/fake/model")
    mock_rec = mock_rec_cls.return_value
    mock_rec.AcceptWaveform.return_value = 0
    mock_rec.PartialResult.return_value = json.dumps({"partial": "hello"})

    result = engine.process_audio(b"\x00" * 100)
    assert result.text == "hello"
    assert result.is_final is False


@patch("dictation.stt.KaldiRecognizer")
@patch("dictation.stt.Model")
def test_stt_engine_process_audio_final(mock_model_cls, mock_rec_cls):
    engine = STTEngine(model_path="/fake/model")
    mock_rec = mock_rec_cls.return_value
    mock_rec.AcceptWaveform.return_value = 1
    mock_rec.Result.return_value = json.dumps({"text": "hello world"})

    result = engine.process_audio(b"\x00" * 100)
    assert result.text == "hello world"
    assert result.is_final is True


@patch("dictation.stt.KaldiRecognizer")
@patch("dictation.stt.Model")
def test_stt_engine_reset(mock_model_cls, mock_rec_cls):
    engine = STTEngine(model_path="/fake/model")
    engine.reset()
    # After reset, a new recognizer should be created
    assert mock_rec_cls.call_count == 2


@patch("dictation.stt.Model")
def test_stt_engine_finalize(mock_model_cls):
    engine = STTEngine(model_path="/fake/model")
    with patch.object(engine, "_recognizer") as mock_rec:
        mock_rec.FinalResult.return_value = json.dumps({"text": "final text"})
        result = engine.finalize()
        assert result.text == "final text"
        assert result.is_final is True
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_stt.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dictation.stt'`

**Step 3: Write implementation**

`src/dictation/stt.py`:
```python
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
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_stt.py -v`
Expected: All 7 tests PASS.

**Step 5: Commit**

```bash
git add src/dictation/stt.py tests/test_stt.py
git commit -m "feat: STT engine wrapping Vosk"
```

---

### Task 4: TTS Engine (Piper Wrapper)

**Files:**
- Create: `src/dictation/tts.py`
- Create: `tests/test_tts.py`

**Step 1: Write the failing tests**

`tests/test_tts.py`:
```python
"""Tests for TTS engine."""
import io
import wave
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from dictation.tts import TTSEngine


@patch("dictation.tts.PiperVoice")
def test_tts_engine_init(mock_piper_cls):
    engine = TTSEngine(model_path="/fake/model.onnx")
    mock_piper_cls.load.assert_called_once_with("/fake/model.onnx")


@patch("dictation.tts.PiperVoice")
def test_tts_synthesize_wav_bytes(mock_piper_cls):
    mock_voice = MagicMock()
    mock_piper_cls.load.return_value = mock_voice

    # Mock synthesize_wav to write valid WAV data
    def fake_synthesize_wav(text, wav_file, **kwargs):
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\x00" * 100)

    mock_voice.synthesize_wav.side_effect = fake_synthesize_wav

    engine = TTSEngine(model_path="/fake/model.onnx")
    wav_bytes = engine.synthesize(text="hello")
    assert len(wav_bytes) > 0
    # Verify it's valid WAV
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2


@patch("dictation.tts.PiperVoice")
def test_tts_synthesize_to_file(mock_piper_cls, tmp_path):
    mock_voice = MagicMock()
    mock_piper_cls.load.return_value = mock_voice

    def fake_synthesize_wav(text, wav_file, **kwargs):
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\x00" * 100)

    mock_voice.synthesize_wav.side_effect = fake_synthesize_wav

    engine = TTSEngine(model_path="/fake/model.onnx")
    out_path = tmp_path / "output.wav"
    engine.synthesize_to_file("hello", out_path)
    assert out_path.exists()
    assert out_path.stat().st_size > 0
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_tts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dictation.tts'`

**Step 3: Write implementation**

`src/dictation/tts.py`:
```python
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
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_tts.py -v`
Expected: All 3 tests PASS.

**Step 5: Commit**

```bash
git add src/dictation/tts.py tests/test_tts.py
git commit -m "feat: TTS engine wrapping Piper"
```

---

### Task 5: Text Injector (xdotool/wtype)

**Files:**
- Create: `src/dictation/injector.py`
- Create: `tests/test_injector.py`

**Step 1: Write the failing tests**

`tests/test_injector.py`:
```python
"""Tests for text injector."""
import pytest
from unittest.mock import patch, MagicMock
from dictation.injector import TextInjector, detect_display_server


@patch("dictation.injector.subprocess.run")
@patch("dictation.injector.detect_display_server", return_value="x11")
def test_inject_text_x11(mock_detect, mock_run):
    injector = TextInjector()
    injector.type_text("hello world")
    mock_run.assert_called_once_with(
        ["xdotool", "type", "--clearmodifiers", "--", "hello world"],
        check=True,
    )


@patch("dictation.injector.subprocess.run")
@patch("dictation.injector.detect_display_server", return_value="wayland")
def test_inject_text_wayland(mock_detect, mock_run):
    injector = TextInjector()
    injector.type_text("hello world")
    mock_run.assert_called_once_with(
        ["wtype", "--", "hello world"],
        check=True,
    )


@patch("dictation.injector.subprocess.run")
@patch("dictation.injector.detect_display_server", return_value="x11")
def test_inject_backspaces(mock_detect, mock_run):
    injector = TextInjector()
    injector.backspace(5)
    mock_run.assert_called_once_with(
        ["xdotool", "key", "--clearmodifiers"] + ["BackSpace"] * 5,
        check=True,
    )


@patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11"})
def test_detect_display_server_x11():
    assert detect_display_server() == "x11"


@patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"})
def test_detect_display_server_wayland():
    assert detect_display_server() == "wayland"
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_injector.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

`src/dictation/injector.py`:
```python
"""Type text into the focused window using xdotool or wtype."""
from __future__ import annotations

import os
import subprocess


def detect_display_server() -> str:
    """Detect whether running on X11 or Wayland."""
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if "wayland" in session_type:
        return "wayland"
    return "x11"


class TextInjector:
    """Types text into the currently focused window."""

    def __init__(self):
        self._display = detect_display_server()

    def type_text(self, text: str) -> None:
        """Type text into the focused window."""
        if not text:
            return
        if self._display == "wayland":
            subprocess.run(["wtype", "--", text], check=True)
        else:
            subprocess.run(
                ["xdotool", "type", "--clearmodifiers", "--", text],
                check=True,
            )

    def backspace(self, count: int) -> None:
        """Send backspace keys to delete characters."""
        if count <= 0:
            return
        if self._display == "wayland":
            subprocess.run(
                ["wtype", "-k"] + ["BackSpace"] * count,
                check=True,
            )
        else:
            subprocess.run(
                ["xdotool", "key", "--clearmodifiers"] + ["BackSpace"] * count,
                check=True,
            )
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_injector.py -v`
Expected: All 5 tests PASS.

**Step 5: Commit**

```bash
git add src/dictation/injector.py tests/test_injector.py
git commit -m "feat: text injector for xdotool and wtype"
```

---

### Task 6: Audio Playback Module

**Files:**
- Create: `src/dictation/audio.py`
- Create: `tests/test_audio.py`

**Step 1: Write the failing tests**

`tests/test_audio.py`:
```python
"""Tests for audio capture and playback."""
import pytest
from unittest.mock import patch, MagicMock
from dictation.audio import AudioCapture, AudioPlayback


@patch("dictation.audio.sd")
def test_audio_capture_start_stop(mock_sd):
    mock_stream = MagicMock()
    mock_sd.RawInputStream.return_value = mock_stream

    capture = AudioCapture(sample_rate=16000)
    capture.start()
    mock_stream.start.assert_called_once()

    capture.stop()
    mock_stream.stop.assert_called_once()
    mock_stream.close.assert_called_once()


@patch("dictation.audio.sd")
def test_audio_playback_play_bytes(mock_sd):
    playback = AudioPlayback()
    # 16-bit mono silence
    wav_data = b"\x00\x00" * 1000
    playback.play_raw(wav_data, sample_rate=22050)
    mock_sd.play.assert_called_once()
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_audio.py -v`
Expected: FAIL

**Step 3: Write implementation**

`src/dictation/audio.py`:
```python
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
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_audio.py -v`
Expected: All 2 tests PASS.

**Step 5: Commit**

```bash
git add src/dictation/audio.py tests/test_audio.py
git commit -m "feat: audio capture and playback module"
```

---

### Task 7: FastAPI Service

**Files:**
- Create: `src/dictation/api.py`
- Create: `tests/test_api.py`

**Step 1: Write the failing tests**

`tests/test_api.py`:
```python
"""Tests for FastAPI service."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from dictation.api import create_app


@pytest.fixture
def mock_stt():
    return MagicMock()


@pytest.fixture
def mock_tts():
    engine = MagicMock()
    engine.synthesize.return_value = b"RIFF" + b"\x00" * 100
    return engine


@pytest.fixture
def app(mock_stt, mock_tts):
    return create_app(stt_engine=mock_stt, tts_engine=mock_tts)


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_get_status(client):
    resp = await client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data


@pytest.mark.asyncio
async def test_post_tts(client, mock_tts):
    resp = await client.post("/tts", json={"text": "hello"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/wav"
    mock_tts.synthesize.assert_called_once_with("hello")


@pytest.mark.asyncio
async def test_post_tts_missing_text(client):
    resp = await client.post("/tts", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_stt_start(client):
    resp = await client.post("/stt/start")
    assert resp.status_code == 200
    data = resp.json()
    assert "ws_url" in data


@pytest.mark.asyncio
async def test_post_stt_stop(client, mock_stt):
    mock_stt.finalize.return_value = MagicMock(text="hello", is_final=True)
    resp = await client.post("/stt/stop")
    assert resp.status_code == 200
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_api.py -v`
Expected: FAIL

**Step 3: Write implementation**

`src/dictation/api.py`:
```python
"""FastAPI service for dictation."""
from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel


class TTSRequest(BaseModel):
    text: str
    voice: str | None = None


class DictationState:
    """Shared state for the API."""

    def __init__(self, stt_engine=None, tts_engine=None):
        self.stt_engine = stt_engine
        self.tts_engine = tts_engine
        self.is_listening = False


def create_app(stt_engine=None, tts_engine=None) -> FastAPI:
    app = FastAPI(title="Dictation Service")
    state = DictationState(stt_engine=stt_engine, tts_engine=tts_engine)
    app.state.dictation = state

    @app.get("/status")
    async def get_status():
        return {
            "status": "running",
            "listening": state.is_listening,
            "stt_available": state.stt_engine is not None,
            "tts_available": state.tts_engine is not None,
        }

    @app.post("/tts")
    async def post_tts(req: TTSRequest):
        wav_bytes = state.tts_engine.synthesize(req.text)
        return Response(content=wav_bytes, media_type="audio/wav")

    @app.post("/stt/start")
    async def stt_start():
        state.is_listening = True
        return {"status": "listening", "ws_url": "ws://localhost:5678/ws/stt"}

    @app.post("/stt/stop")
    async def stt_stop():
        state.is_listening = False
        result = state.stt_engine.finalize()
        return {"text": result.text, "is_final": result.is_final}

    @app.websocket("/ws/stt")
    async def ws_stt(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_bytes()
                result = state.stt_engine.process_audio(data)
                await websocket.send_json(
                    {"text": result.text, "is_final": result.is_final}
                )
        except WebSocketDisconnect:
            pass

    return app
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_api.py -v`
Expected: All 5 tests PASS.

**Step 5: Commit**

```bash
git add src/dictation/api.py tests/test_api.py
git commit -m "feat: FastAPI service with REST and WebSocket endpoints"
```

---

### Task 8: Model Manager

**Files:**
- Create: `src/dictation/models.py`
- Create: `tests/test_models.py`

**Step 1: Write the failing tests**

`tests/test_models.py`:
```python
"""Tests for model management."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from dictation.models import ModelManager


def test_model_manager_default_dir():
    mgr = ModelManager()
    assert mgr.models_dir == Path.home() / ".local" / "share" / "dictation" / "models"


def test_model_manager_custom_dir(tmp_path):
    mgr = ModelManager(models_dir=tmp_path)
    assert mgr.models_dir == tmp_path


def test_vosk_model_path(tmp_path):
    mgr = ModelManager(models_dir=tmp_path)
    path = mgr.vosk_model_path("vosk-model-small-en-us-0.15")
    assert path == tmp_path / "vosk" / "vosk-model-small-en-us-0.15"


def test_piper_model_path(tmp_path):
    mgr = ModelManager(models_dir=tmp_path)
    path = mgr.piper_model_path("en_US-lessac-medium")
    assert path == tmp_path / "piper" / "en_US-lessac-medium.onnx"


def test_vosk_model_available(tmp_path):
    mgr = ModelManager(models_dir=tmp_path)
    # Not downloaded yet
    assert mgr.is_vosk_model_available("vosk-model-small-en-us-0.15") is False
    # Create the directory
    model_dir = tmp_path / "vosk" / "vosk-model-small-en-us-0.15"
    model_dir.mkdir(parents=True)
    assert mgr.is_vosk_model_available("vosk-model-small-en-us-0.15") is True


def test_piper_model_available(tmp_path):
    mgr = ModelManager(models_dir=tmp_path)
    assert mgr.is_piper_model_available("en_US-lessac-medium") is False
    model_file = tmp_path / "piper" / "en_US-lessac-medium.onnx"
    model_file.parent.mkdir(parents=True)
    model_file.touch()
    (tmp_path / "piper" / "en_US-lessac-medium.onnx.json").touch()
    assert mgr.is_piper_model_available("en_US-lessac-medium") is True
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL

**Step 3: Write implementation**

`src/dictation/models.py`:
```python
"""Model download and management."""
from __future__ import annotations

from pathlib import Path


class ModelManager:
    """Manages STT and TTS model storage and availability."""

    def __init__(self, models_dir: Path | None = None):
        self.models_dir = models_dir or (
            Path.home() / ".local" / "share" / "dictation" / "models"
        )

    def vosk_model_path(self, model_name: str) -> Path:
        return self.models_dir / "vosk" / model_name

    def piper_model_path(self, voice_name: str) -> Path:
        return self.models_dir / "piper" / f"{voice_name}.onnx"

    def piper_config_path(self, voice_name: str) -> Path:
        return self.models_dir / "piper" / f"{voice_name}.onnx.json"

    def is_vosk_model_available(self, model_name: str) -> bool:
        return self.vosk_model_path(model_name).is_dir()

    def is_piper_model_available(self, voice_name: str) -> bool:
        return (
            self.piper_model_path(voice_name).is_file()
            and self.piper_config_path(voice_name).is_file()
        )

    def ensure_dirs(self) -> None:
        """Create model directories if they don't exist."""
        (self.models_dir / "vosk").mkdir(parents=True, exist_ok=True)
        (self.models_dir / "piper").mkdir(parents=True, exist_ok=True)

    def download_vosk_model(self, model_name: str) -> Path:
        """Download a Vosk model. Uses Vosk's built-in download."""
        self.ensure_dirs()
        from vosk import Model
        # Vosk auto-downloads when model_name is used
        model = Model(model_name=model_name)
        # Copy/symlink to our models dir if needed
        return self.vosk_model_path(model_name)

    def download_piper_voice(self, voice_name: str) -> Path:
        """Download a Piper voice model."""
        self.ensure_dirs()
        piper_dir = self.models_dir / "piper"
        from piper.download_voices import download_voice
        download_voice(voice_name, piper_dir)
        return self.piper_model_path(voice_name)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_models.py -v`
Expected: All 6 tests PASS.

**Step 5: Commit**

```bash
git add src/dictation/models.py tests/test_models.py
git commit -m "feat: model manager for Vosk and Piper models"
```

---

### Task 9: Dictation Daemon

**Files:**
- Create: `src/dictation/daemon.py`
- Create: `tests/test_daemon.py`

**Step 1: Write the failing tests**

`tests/test_daemon.py`:
```python
"""Tests for the dictation daemon."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from dictation.daemon import DictationDaemon


@patch("dictation.daemon.AudioCapture")
@patch("dictation.daemon.STTEngine")
@patch("dictation.daemon.TextInjector")
def test_daemon_toggle_on(mock_injector_cls, mock_stt_cls, mock_capture_cls):
    daemon = DictationDaemon.__new__(DictationDaemon)
    daemon._stt = mock_stt_cls.return_value
    daemon._capture = mock_capture_cls.return_value
    daemon._injector = mock_injector_cls.return_value
    daemon._is_listening = False
    daemon._last_partial = ""

    daemon.toggle_dictation()
    assert daemon._is_listening is True
    daemon._capture.start.assert_called_once()


@patch("dictation.daemon.AudioCapture")
@patch("dictation.daemon.STTEngine")
@patch("dictation.daemon.TextInjector")
def test_daemon_toggle_off(mock_injector_cls, mock_stt_cls, mock_capture_cls):
    daemon = DictationDaemon.__new__(DictationDaemon)
    daemon._stt = mock_stt_cls.return_value
    daemon._stt.finalize.return_value = MagicMock(text="final", is_final=True)
    daemon._capture = mock_capture_cls.return_value
    daemon._injector = mock_injector_cls.return_value
    daemon._is_listening = True
    daemon._last_partial = "part"

    daemon.toggle_dictation()
    assert daemon._is_listening is False
    daemon._capture.stop.assert_called_once()
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_daemon.py -v`
Expected: FAIL

**Step 3: Write implementation**

`src/dictation/daemon.py`:
```python
"""Dictation daemon — ties STT, TTS, audio, hotkey, and API together."""
from __future__ import annotations

import logging
import threading

from dictation.audio import AudioCapture, AudioPlayback
from dictation.config import DictationConfig, load_config
from dictation.injector import TextInjector
from dictation.models import ModelManager
from dictation.stt import STTEngine

logger = logging.getLogger(__name__)


class DictationDaemon:
    """Main daemon that orchestrates dictation."""

    def __init__(self, config: DictationConfig | None = None):
        self._config = config or load_config()
        self._model_mgr = ModelManager(models_dir=self._config.models_dir)
        self._injector = TextInjector()
        self._capture = AudioCapture(sample_rate=16000)
        self._playback = AudioPlayback()
        self._is_listening = False
        self._last_partial = ""
        self._listen_thread: threading.Thread | None = None

        # Lazy-init engines
        self._stt: STTEngine | None = None
        self._tts = None

    def _ensure_stt(self) -> STTEngine:
        if self._stt is None:
            model_path = self._model_mgr.vosk_model_path(self._config.stt_model)
            if not self._model_mgr.is_vosk_model_available(self._config.stt_model):
                logger.info("Downloading Vosk model: %s", self._config.stt_model)
                self._model_mgr.download_vosk_model(self._config.stt_model)
            self._stt = STTEngine(model_path=str(model_path))
        return self._stt

    def _ensure_tts(self):
        if self._tts is None:
            from dictation.tts import TTSEngine
            model_path = self._model_mgr.piper_model_path(self._config.tts_voice)
            if not self._model_mgr.is_piper_model_available(self._config.tts_voice):
                logger.info("Downloading Piper voice: %s", self._config.tts_voice)
                self._model_mgr.download_piper_voice(self._config.tts_voice)
            self._tts = TTSEngine(model_path=model_path)
        return self._tts

    def toggle_dictation(self) -> None:
        """Toggle dictation on/off."""
        if self._is_listening:
            self._stop_listening()
        else:
            self._start_listening()

    def _start_listening(self) -> None:
        self._is_listening = True
        self._last_partial = ""
        stt = self._ensure_stt()
        stt.reset()
        self._capture.start()
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listen_thread.start()
        logger.info("Dictation started")

    def _stop_listening(self) -> None:
        self._is_listening = False
        self._capture.stop()
        if self._stt:
            result = self._stt.finalize()
            if result.text and self._last_partial:
                # Replace partial with final
                self._injector.backspace(len(self._last_partial))
                self._injector.type_text(result.text)
        self._last_partial = ""
        logger.info("Dictation stopped")

    def _listen_loop(self) -> None:
        """Background thread that processes audio chunks."""
        while self._is_listening:
            data = self._capture.read(timeout=0.5)
            if data is None:
                continue
            result = self._stt.process_audio(data)
            if result.text:
                if result.is_final:
                    if self._last_partial:
                        self._injector.backspace(len(self._last_partial))
                    self._injector.type_text(result.text + " ")
                    self._last_partial = ""
                else:
                    if self._last_partial:
                        self._injector.backspace(len(self._last_partial))
                    self._injector.type_text(result.text)
                    self._last_partial = result.text

    @property
    def is_listening(self) -> bool:
        return self._is_listening

    def say(self, text: str) -> None:
        """Speak text aloud using TTS."""
        tts = self._ensure_tts()
        wav_bytes = tts.synthesize(text)
        self._playback.play_raw(wav_bytes[44:])  # skip WAV header

    def run(self) -> None:
        """Run the daemon with hotkey listener and API server."""
        import uvicorn
        from pynput import keyboard
        from dictation.api import create_app

        stt = self._ensure_stt()
        tts = self._ensure_tts()
        app = create_app(stt_engine=stt, tts_engine=tts)

        # Parse hotkey
        hotkey_str = self._config.hotkey.replace("super", "<cmd>")
        hotkey = keyboard.HotKey(
            keyboard.HotKey.parse(f"<{hotkey_str}>")
            if "+" in hotkey_str
            else keyboard.HotKey.parse(hotkey_str),
            self.toggle_dictation,
        )

        def on_press(key):
            hotkey.press(key)

        def on_release(key):
            hotkey.release(key)

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        logger.info("Hotkey '%s' registered. Listening on port %d", self._config.hotkey, self._config.api_port)

        uvicorn.run(app, host="127.0.0.1", port=self._config.api_port, log_level="info")
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_daemon.py -v`
Expected: All 2 tests PASS.

**Step 5: Commit**

```bash
git add src/dictation/daemon.py tests/test_daemon.py
git commit -m "feat: dictation daemon with hotkey and audio loop"
```

---

### Task 10: CLI Entry Point

**Files:**
- Create: `src/dictation/cli.py`
- Create: `tests/test_cli.py`

**Step 1: Write the failing tests**

`tests/test_cli.py`:
```python
"""Tests for CLI."""
import pytest
from unittest.mock import patch, MagicMock
from dictation.cli import main, parse_args


def test_parse_args_start():
    args = parse_args(["start"])
    assert args.command == "start"


def test_parse_args_stop():
    args = parse_args(["stop"])
    assert args.command == "stop"


def test_parse_args_say():
    args = parse_args(["say", "hello world"])
    assert args.command == "say"
    assert args.text == "hello world"


def test_parse_args_listen():
    args = parse_args(["listen"])
    assert args.command == "listen"


def test_parse_args_status():
    args = parse_args(["status"])
    assert args.command == "status"


@patch("dictation.cli.httpx")
def test_status_command(mock_httpx):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "running", "listening": False}
    mock_resp.status_code = 200
    mock_httpx.get.return_value = mock_resp

    with patch("sys.argv", ["dictation", "status"]):
        # Should not raise
        main()
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL

**Step 3: Write implementation**

`src/dictation/cli.py`:
```python
"""CLI entry point for the dictation service."""
from __future__ import annotations

import argparse
import sys

import httpx

from dictation.config import load_config

DEFAULT_BASE_URL = "http://127.0.0.1:{port}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dictation",
        description="Lightweight local dictation service",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("start", help="Start the dictation daemon")
    sub.add_parser("stop", help="Stop the dictation daemon")
    sub.add_parser("status", help="Show service status")
    sub.add_parser("listen", help="One-shot STT, print transcript to stdout")

    say_parser = sub.add_parser("say", help="Speak text aloud")
    say_parser.add_argument("text", help="Text to speak")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    config = load_config()
    base_url = DEFAULT_BASE_URL.format(port=config.api_port)

    if args.command == "start":
        _cmd_start(config)
    elif args.command == "stop":
        _cmd_stop(base_url)
    elif args.command == "status":
        _cmd_status(base_url)
    elif args.command == "say":
        _cmd_say(base_url, args.text)
    elif args.command == "listen":
        _cmd_listen(base_url)


def _cmd_start(config):
    from dictation.daemon import DictationDaemon
    daemon = DictationDaemon(config=config)
    print(f"Starting dictation daemon on port {config.api_port}...")
    print(f"Hotkey: {config.hotkey}")
    daemon.run()


def _cmd_stop(base_url: str):
    try:
        resp = httpx.post(f"{base_url}/stt/stop")
        print("Dictation stopped.")
    except httpx.ConnectError:
        print("Daemon is not running.", file=sys.stderr)
        sys.exit(1)


def _cmd_status(base_url: str):
    try:
        resp = httpx.get(f"{base_url}/status")
        data = resp.json()
        print(f"Status: {data['status']}")
        print(f"Listening: {data['listening']}")
        print(f"STT available: {data.get('stt_available', False)}")
        print(f"TTS available: {data.get('tts_available', False)}")
    except httpx.ConnectError:
        print("Daemon is not running.", file=sys.stderr)
        sys.exit(1)


def _cmd_say(base_url: str, text: str):
    try:
        resp = httpx.post(f"{base_url}/tts", json={"text": text})
        if resp.status_code == 200:
            from dictation.audio import AudioPlayback
            playback = AudioPlayback()
            playback.play_raw(resp.content[44:])  # skip WAV header
        else:
            print(f"Error: {resp.status_code}", file=sys.stderr)
    except httpx.ConnectError:
        print("Daemon is not running.", file=sys.stderr)
        sys.exit(1)


def _cmd_listen(base_url: str):
    try:
        import websockets.sync.client as ws_client
        resp = httpx.post(f"{base_url}/stt/start")
        ws_url = resp.json()["ws_url"]

        from dictation.audio import AudioCapture
        capture = AudioCapture(sample_rate=16000)
        capture.start()

        print("Listening... Press Ctrl+C to stop.")
        with ws_client.connect(ws_url) as ws:
            try:
                while True:
                    data = capture.read(timeout=0.5)
                    if data:
                        ws.send(data)
                        result = ws.recv()
                        import json
                        parsed = json.loads(result)
                        if parsed.get("is_final"):
                            print(parsed["text"])
                        else:
                            print(f"... {parsed['text']}", end="\r")
            except KeyboardInterrupt:
                pass
            finally:
                capture.stop()
                httpx.post(f"{base_url}/stt/stop")
                print("\nDone.")
    except httpx.ConnectError:
        print("Daemon is not running.", file=sys.stderr)
        sys.exit(1)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: All 6 tests PASS.

**Step 5: Commit**

```bash
git add src/dictation/cli.py tests/test_cli.py
git commit -m "feat: CLI entry point with start/stop/status/say/listen"
```

---

### Task 11: Systemd Service File

**Files:**
- Create: `contrib/dictation.service`

**Step 1: Create the systemd unit file**

`contrib/dictation.service`:
```ini
[Unit]
Description=Dictation Service (STT/TTS)
After=network.target sound.target

[Service]
Type=simple
ExecStart=%h/.venv/bin/dictation start
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

**Step 2: Commit**

```bash
git add contrib/dictation.service
git commit -m "feat: systemd user service file"
```

---

### Task 12: Integration Smoke Test

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write the integration test**

`tests/test_integration.py`:
```python
"""Integration smoke test — verifies modules wire together."""
import pytest
from unittest.mock import patch, MagicMock
from dictation.config import DictationConfig
from dictation.daemon import DictationDaemon


@patch("dictation.daemon.AudioCapture")
@patch("dictation.daemon.STTEngine")
@patch("dictation.daemon.TextInjector")
def test_daemon_creates_with_config(mock_inj, mock_stt, mock_cap):
    config = DictationConfig(api_port=9999, hotkey="ctrl+d")

    with patch("dictation.daemon.ModelManager") as mock_mgr_cls:
        mock_mgr = mock_mgr_cls.return_value
        mock_mgr.is_vosk_model_available.return_value = True
        mock_mgr.vosk_model_path.return_value = "/fake/model"

        daemon = DictationDaemon(config=config)
        assert daemon._config.api_port == 9999
        assert daemon.is_listening is False
```

**Step 2: Run test**

Run: `python -m pytest tests/test_integration.py -v`
Expected: PASS.

**Step 3: Run full test suite**

Run: `python -m pytest -v`
Expected: All tests PASS.

**Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: integration smoke test for daemon wiring"
```
