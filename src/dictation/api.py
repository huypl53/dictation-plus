"""FastAPI service for dictation — OpenAI-compatible API."""
from __future__ import annotations

import array
import asyncio
import base64
import io
import struct
import uuid
import wave
from typing import Any, Protocol

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel

from dictation.pool import EnginePool
from dictation.stt import STTResult


class STTEngineProto(Protocol):
    """Protocol shared by STTEngine and WhisperSTTEngine."""

    def process_audio(self, data: bytes) -> STTResult: ...
    def finalize(self) -> STTResult: ...
    def reset(self) -> None: ...


class TTSEngineProto(Protocol):
    """Protocol for TTS engines."""

    def synthesize(self, text: str) -> bytes: ...


class SpeechRequest(BaseModel):
    """OpenAI-compatible TTS request: POST /v1/audio/speech."""
    model: str
    input: str
    voice: str = "alloy"
    response_format: str = "wav"
    speed: float = 1.0


class DictationState:
    """Shared state for the API."""

    def __init__(
        self,
        stt_pool: EnginePool[STTEngineProto] | None = None,
        tts_pool: EnginePool[TTSEngineProto] | None = None,
    ):
        self.stt_pool: EnginePool[STTEngineProto] | None = stt_pool
        self.tts_pool: EnginePool[TTSEngineProto] | None = tts_pool
        self.is_listening: bool = False


def create_app(
    stt_pool: EnginePool[STTEngineProto] | None = None,
    tts_pool: EnginePool[TTSEngineProto] | None = None,
) -> FastAPI:
    app = FastAPI(title="Dictation Service")
    state = DictationState(stt_pool=stt_pool, tts_pool=tts_pool)
    app.state.dictation = state

    @app.get("/status")
    async def get_status() -> dict[str, object]:
        return {
            "status": "running",
            "listening": state.is_listening,
            "stt_available": state.stt_pool is not None,
            "tts_available": state.tts_pool is not None,
        }

    @app.post("/stop")
    async def stop_listening() -> dict[str, str]:
        state.is_listening = False
        return {"status": "stopped", "text": ""}

    # ── TTS: POST /v1/audio/speech ──────────────────────────────────────

    @app.post("/v1/audio/speech")
    async def create_speech(req: SpeechRequest) -> Response:
        if state.tts_pool is None:
            raise HTTPException(status_code=503, detail="TTS engine not available")
        if req.response_format not in ("wav", "pcm"):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported response_format '{req.response_format}'. Supported: wav, pcm",
            )
        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        async with state.tts_pool.checkout() as tts:
            wav_bytes: bytes = await loop.run_in_executor(None, tts.synthesize, req.input)
        if req.response_format == "pcm":
            pcm_data: bytes = _wav_to_pcm(wav_bytes)
            return Response(content=pcm_data, media_type="audio/pcm")
        return Response(content=wav_bytes, media_type="audio/wav")

    # ── STT: POST /v1/audio/transcriptions ──────────────────────────────

    @app.post("/v1/audio/transcriptions")
    async def create_transcription(
        file: UploadFile = File(...),
        model: str = Form("whisper-1"),
        language: str | None = Form(None),
        response_format: str = Form("json"),
    ):
        if state.stt_pool is None:
            raise HTTPException(status_code=503, detail="STT engine not available")

        audio_bytes: bytes = await file.read()

        # Normalize audio to 16kHz mono 16-bit PCM
        pcm_bytes: bytes
        pcm_bytes, _, _, _ = _extract_and_normalize(audio_bytes)
        duration: float = len(pcm_bytes) / (16000 * 2)

        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        async with state.stt_pool.checkout() as stt:
            chunk_size: int = 4000
            for i in range(0, len(pcm_bytes), chunk_size):
                await loop.run_in_executor(
                    None, stt.process_audio, pcm_bytes[i : i + chunk_size]
                )
            result: STTResult = await loop.run_in_executor(None, stt.finalize)

        if response_format == "text":
            return PlainTextResponse(result.text)
        elif response_format == "verbose_json":
            return {
                "text": result.text,
                "language": language or "en",
                "duration": round(duration, 2),
            }
        else:
            return {"text": result.text}

    # ── Realtime WebSocket: /v1/realtime ─────────────────────────────────

    @app.websocket("/v1/realtime")
    async def realtime_transcription(websocket: WebSocket) -> None:
        if state.stt_pool is None:
            await websocket.close(code=1013, reason="STT engine not available")
            return

        async with state.stt_pool.checkout() as stt:
            await websocket.accept()

            loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
            session_id: str = f"sess_{uuid.uuid4().hex[:24]}"
            session_config: dict[str, Any] = {
                "id": session_id,
                "input_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1",
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500,
                },
            }
            item_counter: int = 0

            await websocket.send_json({
                "type": "session.created",
                "session": session_config,
            })

            await loop.run_in_executor(None, stt.reset)

            try:
                while True:
                    message: dict[str, Any] = await websocket.receive_json()
                    event_type: str = message.get("type", "")

                    if event_type == "transcription_session.update":
                        new_session: dict[str, Any] = message.get("session", {})
                        if "input_audio_format" in new_session:
                            session_config["input_audio_format"] = new_session["input_audio_format"]
                        if "input_audio_transcription" in new_session:
                            session_config["input_audio_transcription"] = new_session["input_audio_transcription"]
                        if "turn_detection" in new_session:
                            session_config["turn_detection"] = new_session["turn_detection"]
                        await websocket.send_json({
                            "type": "session.updated",
                            "session": session_config,
                        })

                    elif event_type == "input_audio_buffer.append":
                        audio_b64: str = message.get("audio", "")
                        audio_data: bytes = base64.b64decode(audio_b64)
                        result: STTResult = await loop.run_in_executor(
                            None, stt.process_audio, audio_data
                        )
                        if result.text:
                            await websocket.send_json({
                                "type": "conversation.item.input_audio_transcription.delta",
                                "item_id": f"item_{item_counter:03d}",
                                "content_index": 0,
                                "delta": result.text,
                            })

                    elif event_type == "input_audio_buffer.commit":
                        result = await loop.run_in_executor(None, stt.finalize)
                        await websocket.send_json({
                            "type": "input_audio_buffer.committed",
                            "item_id": f"item_{item_counter:03d}",
                        })
                        await websocket.send_json({
                            "type": "conversation.item.input_audio_transcription.completed",
                            "item_id": f"item_{item_counter:03d}",
                            "content_index": 0,
                            "transcript": result.text,
                        })
                        item_counter += 1
                        await loop.run_in_executor(None, stt.reset)

                    elif event_type == "input_audio_buffer.clear":
                        await loop.run_in_executor(None, stt.reset)
                        await websocket.send_json({
                            "type": "input_audio_buffer.cleared",
                        })

            except WebSocketDisconnect:
                pass

    return app


def _wav_to_pcm(wav_bytes: bytes) -> bytes:
    """Extract raw PCM frames from a WAV container."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        return wf.readframes(wf.getnframes())


_TARGET_RATE: int = 16000


def _extract_and_normalize(audio_bytes: bytes) -> tuple[bytes, int, int, int]:
    """Extract PCM from WAV and normalize to 16kHz mono 16-bit.

    Returns (pcm_bytes, sample_rate, n_channels, sampwidth) after normalization.
    Non-WAV input is assumed to already be 16kHz mono 16-bit PCM.
    """
    if audio_bytes[:4] == b"RIFF":
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                n_channels: int = wf.getnchannels()
                sampwidth: int = wf.getsampwidth()
                orig_rate: int = wf.getframerate()
                raw_data: bytes = wf.readframes(wf.getnframes())

            # Convert to mono by averaging channels
            if n_channels > 1:
                raw_data = _to_mono(raw_data, sampwidth, n_channels)

            # Convert to 16-bit
            if sampwidth == 1:
                # 8-bit unsigned → 16-bit signed
                raw_data = bytes(
                    b
                    for sample in raw_data
                    for b in struct.pack("<h", (sample - 128) << 8)
                )
            elif sampwidth == 4:
                # 32-bit signed → 16-bit signed (take upper 16 bits)
                samples = struct.unpack(f"<{len(raw_data) // 4}i", raw_data)
                raw_data = struct.pack(f"<{len(samples)}h", *(s >> 16 for s in samples))

            # Resample to 16kHz via linear interpolation
            if orig_rate != _TARGET_RATE:
                raw_data = _resample(raw_data, orig_rate, _TARGET_RATE)

            return raw_data, _TARGET_RATE, 1, 2
        except wave.Error:
            pass
    # Assume raw 16kHz mono 16-bit PCM
    return audio_bytes, _TARGET_RATE, 1, 2


def _to_mono(data: bytes, sampwidth: int, n_channels: int) -> bytes:
    """Average interleaved channels down to mono."""
    n_frames: int = len(data) // (sampwidth * n_channels)
    fmt: str = {1: "B", 2: "h", 4: "i"}[sampwidth]
    samples: tuple[int, ...] = struct.unpack(f"<{n_frames * n_channels}{fmt}", data)
    mono: list[int] = []
    for i in range(0, len(samples), n_channels):
        avg: int = sum(samples[i : i + n_channels]) // n_channels
        mono.append(avg)
    return struct.pack(f"<{len(mono)}{fmt}", *mono)


def _resample(data: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Resample 16-bit mono PCM via linear interpolation."""
    samples: array.array[int] = array.array("h")
    samples.frombytes(data)
    n: int = len(samples)
    if n == 0:
        return data
    ratio: float = src_rate / dst_rate
    out_len: int = int(n / ratio)
    out: array.array[int] = array.array("h", [0] * out_len)
    for i in range(out_len):
        pos: float = i * ratio
        idx: int = int(pos)
        frac: float = pos - idx
        if idx + 1 < n:
            out[i] = int(samples[idx] * (1 - frac) + samples[idx + 1] * frac)
        else:
            out[i] = samples[min(idx, n - 1)]
    return out.tobytes()
