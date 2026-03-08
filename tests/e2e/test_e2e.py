"""End-to-end tests with real Vosk STT and Piper TTS engines."""
from __future__ import annotations

import base64
import io
import json
import os
import subprocess
import sys
import threading
import time
import wave

import httpx
import pytest
import uvicorn
import websockets.sync.client as ws_client

from dictation.api import create_app
from dictation.stt import STTEngine
from dictation.tts import TTSEngine

MODELS_DIR = os.environ.get("DICTATION_MODELS_DIR", "/models")
VOSK_MODEL = os.path.join(MODELS_DIR, "vosk", "vosk-model-small-en-us-0.15")
PIPER_MODEL = os.path.join(MODELS_DIR, "piper", "en_US-lessac-medium.onnx")
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 15678  # Use non-default port to avoid conflicts
BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"


def resample_wav_to_16k(wav_bytes: bytes) -> bytes:
    """Resample WAV audio to 16kHz mono 16-bit PCM for Vosk."""
    from dictation.api import _extract_and_normalize

    pcm_data, rate, channels, sampwidth = _extract_and_normalize(wav_bytes)

    # Write as 16kHz mono WAV
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(pcm_data)
    return buf.getvalue()


@pytest.fixture(scope="module")
def running_server():
    """Start FastAPI server with real engines, shared across all tests."""
    stt_engine = STTEngine(model_path=VOSK_MODEL)
    tts_engine = TTSEngine(model_path=PIPER_MODEL)
    app = create_app(stt_engine=stt_engine, tts_engine=tts_engine)

    config = uvicorn.Config(app, host=SERVER_HOST, port=SERVER_PORT, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to be ready
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(f"{BASE_URL}/status", timeout=1)
            if resp.status_code == 200:
                break
        except (httpx.ConnectError, httpx.ReadTimeout):
            pass
        time.sleep(0.2)
    else:
        raise RuntimeError("Server did not start within 15 seconds")

    yield {"base_url": BASE_URL, "stt_engine": stt_engine, "tts_engine": tts_engine}

    server.should_exit = True
    thread.join(timeout=5)


def test_status(running_server):
    """GET /status returns running with engines available."""
    resp = httpx.get(f"{running_server['base_url']}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    assert data["stt_available"] is True
    assert data["tts_available"] is True


def test_tts_real_synthesis(running_server):
    """POST /v1/audio/speech returns valid WAV audio from real Piper."""
    resp = httpx.post(
        f"{running_server['base_url']}/v1/audio/speech",
        json={"model": "piper", "input": "hello", "voice": "alloy"},
        timeout=30,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/wav"

    # Verify it's a valid WAV
    wav_bytes = resp.content
    assert len(wav_bytes) > 44  # WAV header is 44 bytes minimum
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getnchannels() >= 1
        assert wf.getsampwidth() == 2  # 16-bit
        assert wf.getframerate() > 0
        assert wf.getnframes() > 0
        duration = wf.getnframes() / wf.getframerate()
    print(f"\n  TTS 'hello' → WAV: {len(wav_bytes)} bytes, "
          f"{wf.getframerate()}Hz, {duration:.2f}s")


def test_stt_via_websocket(running_server):
    """TTS 'hello' then feed resampled audio to STT via realtime WebSocket."""
    # Generate audio via TTS
    resp = httpx.post(
        f"{running_server['base_url']}/v1/audio/speech",
        json={"model": "piper", "input": "hello", "voice": "alloy"},
        timeout=30,
    )
    wav_bytes = resample_wav_to_16k(resp.content)

    # Extract raw PCM (skip WAV header)
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        pcm_data = wf.readframes(wf.getnframes())

    # Reset STT engine for a fresh recognition
    running_server["stt_engine"].reset()

    # Feed audio via realtime WebSocket using OpenAI protocol
    ws_url = f"ws://{SERVER_HOST}:{SERVER_PORT}/v1/realtime?intent=transcription"
    collected_text = []
    chunk_size = 4000  # ~125ms of 16kHz 16-bit mono

    with ws_client.connect(ws_url) as ws:
        # Receive session.created
        msg = json.loads(ws.recv())
        assert msg["type"] == "session.created"

        # Send audio chunks
        for i in range(0, len(pcm_data), chunk_size):
            chunk = pcm_data[i : i + chunk_size]
            ws.send(json.dumps({
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(chunk).decode(),
            }))
            # Check for any delta responses
            try:
                result = json.loads(ws.recv(timeout=0.1))
                if result["type"] == "conversation.item.input_audio_transcription.delta":
                    collected_text.append(result["delta"])
            except TimeoutError:
                pass

        # Commit the buffer to get final transcription
        ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
        # Receive committed + completed events
        while True:
            result = json.loads(ws.recv(timeout=5.0))
            if result["type"] == "conversation.item.input_audio_transcription.completed":
                if result["transcript"]:
                    collected_text.append(result["transcript"])
                break

    all_text = " ".join(collected_text).lower()
    print(f"\n  TTS 'hello' → STT heard: '{all_text}'")
    assert len(all_text) > 0, "STT produced no text from TTS audio"


def test_stt_batch_transcription(running_server):
    """TTS generates audio, then POST /v1/audio/transcriptions transcribes it."""
    # Generate audio via TTS
    resp = httpx.post(
        f"{running_server['base_url']}/v1/audio/speech",
        json={"model": "piper", "input": "hello", "voice": "alloy"},
        timeout=30,
    )
    wav_bytes = resample_wav_to_16k(resp.content)

    # Reset STT engine
    running_server["stt_engine"].reset()

    # Submit audio for batch transcription
    resp = httpx.post(
        f"{running_server['base_url']}/v1/audio/transcriptions",
        files={"file": ("audio.wav", wav_bytes, "audio/wav")},
        data={"model": "whisper-1"},
        timeout=30,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "text" in data
    print(f"\n  Batch transcription: '{data['text']}'")
    assert len(data["text"]) > 0, "Batch transcription produced no text"


def test_round_trip(running_server):
    """TTS generates audio, STT transcribes it, verify keywords present."""
    test_phrase = "testing one two three"

    # Generate audio
    resp = httpx.post(
        f"{running_server['base_url']}/v1/audio/speech",
        json={"model": "piper", "input": test_phrase, "voice": "alloy"},
        timeout=30,
    )
    wav_bytes = resample_wav_to_16k(resp.content)

    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        pcm_data = wf.readframes(wf.getnframes())

    # Reset STT engine
    running_server["stt_engine"].reset()

    # Feed all audio through STT directly (not via server to avoid state conflicts)
    stt = running_server["stt_engine"]
    chunk_size = 4000
    collected = []

    for i in range(0, len(pcm_data), chunk_size):
        chunk = pcm_data[i : i + chunk_size]
        result = stt.process_audio(chunk)
        if result.text:
            collected.append(result.text)

    final = stt.finalize()
    if final.text:
        collected.append(final.text)

    all_text = " ".join(collected).lower()

    print(f"\n  TTS '{test_phrase}' → STT heard: '{all_text}'")

    # Fuzzy match: at least 2 of the keywords should be recognized
    keywords = ["testing", "one", "two", "three"]
    matches = sum(1 for kw in keywords if kw in all_text)
    print(f"  Keyword matches: {matches}/4 {keywords}")
    assert matches >= 2, (
        f"Expected at least 2 keywords from {keywords} in transcription, "
        f"got {matches}. Full text: '{all_text}'"
    )


def test_cli_status(running_server):
    """CLI status logic works against the running server."""
    from dictation.cli import _cmd_status
    from io import StringIO
    import contextlib

    buf = StringIO()
    with contextlib.redirect_stdout(buf):
        _cmd_status(running_server["base_url"])

    output = buf.getvalue()
    print(f"\n  CLI status output:\n    {output.strip().replace(chr(10), chr(10) + '    ')}")
    assert "running" in output.lower()
