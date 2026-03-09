"""Tests for FastAPI service (OpenAI-compatible API)."""
import base64
import io
import json
import wave

import pytest
from unittest.mock import MagicMock
from httpx import AsyncClient, ASGITransport
from dictation.api import create_app
from dictation.pool import EnginePool
from dictation.stt import STTResult


@pytest.fixture
def mock_stt():
    engine = MagicMock()
    engine.process_audio.return_value = STTResult(text="", is_final=False)
    engine.finalize.return_value = STTResult(text="hello world", is_final=True)
    return engine


def _make_wav(pcm_data: bytes = b"\x00" * 100) -> bytes:
    """Build a valid WAV file from raw PCM."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        wf.writeframes(pcm_data)
    return buf.getvalue()


@pytest.fixture
def mock_tts():
    engine = MagicMock()
    engine.synthesize.return_value = _make_wav()
    return engine


@pytest.fixture
def app(mock_stt, mock_tts):
    stt_pool = EnginePool(lambda: mock_stt, max_size=1)
    tts_pool = EnginePool(lambda: mock_tts, max_size=1)
    return create_app(stt_pool=stt_pool, tts_pool=tts_pool)


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── Status ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_status(client):
    resp = await client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    assert data["stt_available"] is True
    assert data["tts_available"] is True


# ── TTS: POST /v1/audio/speech ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_speech(client, mock_tts):
    resp = await client.post(
        "/v1/audio/speech",
        json={"model": "piper", "input": "hello", "voice": "alloy"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/wav"
    mock_tts.synthesize.assert_called_once_with("hello")


@pytest.mark.asyncio
async def test_create_speech_missing_input(client):
    resp = await client.post("/v1/audio/speech", json={"model": "piper"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_speech_unsupported_format(client):
    resp = await client.post(
        "/v1/audio/speech",
        json={"model": "piper", "input": "hi", "voice": "alloy", "response_format": "mp3"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_speech_pcm_format(client, mock_tts):
    resp = await client.post(
        "/v1/audio/speech",
        json={"model": "piper", "input": "hi", "voice": "alloy", "response_format": "pcm"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/pcm"


# ── STT: POST /v1/audio/transcriptions ──────────────────────────────────

@pytest.mark.asyncio
async def test_create_transcription_json(client, mock_stt):
    audio = b"\x00" * 8000  # raw PCM bytes
    resp = await client.post(
        "/v1/audio/transcriptions",
        files={"file": ("audio.raw", audio, "application/octet-stream")},
        data={"model": "whisper-1"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["text"] == "hello world"
    mock_stt.finalize.assert_called_once()


@pytest.mark.asyncio
async def test_create_transcription_text_format(client, mock_stt):
    audio = b"\x00" * 8000
    resp = await client.post(
        "/v1/audio/transcriptions",
        files={"file": ("audio.raw", audio, "application/octet-stream")},
        data={"model": "whisper-1", "response_format": "text"},
    )
    assert resp.status_code == 200
    assert resp.text == "hello world"


@pytest.mark.asyncio
async def test_create_transcription_verbose_json(client, mock_stt):
    audio = b"\x00" * 8000
    resp = await client.post(
        "/v1/audio/transcriptions",
        files={"file": ("audio.raw", audio, "application/octet-stream")},
        data={"model": "whisper-1", "response_format": "verbose_json"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["text"] == "hello world"
    assert "duration" in data
    assert "language" in data


@pytest.mark.asyncio
async def test_create_transcription_wav_input(client, mock_stt):
    """WAV files should have their headers stripped automatically."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00" * 8000)
    wav_bytes = buf.getvalue()

    resp = await client.post(
        "/v1/audio/transcriptions",
        files={"file": ("audio.wav", wav_bytes, "audio/wav")},
        data={"model": "whisper-1"},
    )
    assert resp.status_code == 200
    assert resp.json()["text"] == "hello world"


# ── 503 without engines ─────────────────────────────────────────────────

@pytest.fixture
def app_no_engines():
    return create_app()


@pytest.fixture
async def client_no_engines(app_no_engines):
    transport = ASGITransport(app=app_no_engines)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_speech_503_without_engine(client_no_engines):
    resp = await client_no_engines.post(
        "/v1/audio/speech",
        json={"model": "piper", "input": "hello", "voice": "alloy"},
    )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_transcription_503_without_engine(client_no_engines):
    resp = await client_no_engines.post(
        "/v1/audio/transcriptions",
        files={"file": ("audio.raw", b"\x00" * 100, "application/octet-stream")},
        data={"model": "whisper-1"},
    )
    assert resp.status_code == 503
