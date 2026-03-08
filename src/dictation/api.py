"""FastAPI service for dictation — OpenAI-compatible API."""
from __future__ import annotations

import array
import base64
import io
import struct
import uuid
import wave

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel


class SpeechRequest(BaseModel):
    """OpenAI-compatible TTS request: POST /v1/audio/speech."""
    model: str
    input: str
    voice: str = "alloy"
    response_format: str = "wav"
    speed: float = 1.0


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

    @app.post("/stop")
    async def stop_listening():
        if state.stt_engine is None:
            raise HTTPException(status_code=503, detail="STT engine not available")
        was_listening = state.is_listening
        state.is_listening = False
        if was_listening:
            result = state.stt_engine.finalize()
            state.stt_engine.reset()
            return {"status": "stopped", "text": result.text}
        return {"status": "stopped", "text": ""}

    # ── TTS: POST /v1/audio/speech ──────────────────────────────────────

    @app.post("/v1/audio/speech")
    async def create_speech(req: SpeechRequest):
        if state.tts_engine is None:
            raise HTTPException(status_code=503, detail="TTS engine not available")
        if req.response_format not in ("wav", "pcm"):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported response_format '{req.response_format}'. Supported: wav, pcm",
            )
        wav_bytes = state.tts_engine.synthesize(req.input)
        if req.response_format == "pcm":
            pcm_data = _wav_to_pcm(wav_bytes)
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
        if state.stt_engine is None:
            raise HTTPException(status_code=503, detail="STT engine not available")

        audio_bytes = await file.read()

        # Normalize audio to 16kHz mono 16-bit PCM
        pcm_bytes, sample_rate, n_channels, sampwidth = _extract_and_normalize(audio_bytes)
        duration = len(pcm_bytes) / (16000 * 2)  # normalized to 16kHz 16-bit mono

        # Feed audio in chunks to the STT engine
        chunk_size = 4000
        for i in range(0, len(pcm_bytes), chunk_size):
            state.stt_engine.process_audio(pcm_bytes[i : i + chunk_size])

        result = state.stt_engine.finalize()
        state.stt_engine.reset()

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
    async def realtime_transcription(websocket: WebSocket):
        if state.stt_engine is None:
            await websocket.close(code=1013, reason="STT engine not available")
            return

        await websocket.accept()

        session_id = f"sess_{uuid.uuid4().hex[:24]}"
        session_config = {
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
        item_counter = 0

        # Send session.created
        await websocket.send_json({
            "type": "session.created",
            "session": session_config,
        })

        state.stt_engine.reset()

        try:
            while True:
                message = await websocket.receive_json()
                event_type = message.get("type", "")

                if event_type == "transcription_session.update":
                    new_session = message.get("session", {})
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
                    audio_b64 = message.get("audio", "")
                    audio_data = base64.b64decode(audio_b64)
                    result = state.stt_engine.process_audio(audio_data)
                    if result.text:
                        await websocket.send_json({
                            "type": "conversation.item.input_audio_transcription.delta",
                            "item_id": f"item_{item_counter:03d}",
                            "content_index": 0,
                            "delta": result.text,
                        })

                elif event_type == "input_audio_buffer.commit":
                    result = state.stt_engine.finalize()
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
                    state.stt_engine.reset()

                elif event_type == "input_audio_buffer.clear":
                    state.stt_engine.reset()
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


_TARGET_RATE = 16000


def _extract_and_normalize(audio_bytes: bytes) -> tuple[bytes, int, int, int]:
    """Extract PCM from WAV and normalize to 16kHz mono 16-bit.

    Returns (pcm_bytes, sample_rate, n_channels, sampwidth) after normalization.
    Non-WAV input is assumed to already be 16kHz mono 16-bit PCM.
    """
    if audio_bytes[:4] == b"RIFF":
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                orig_rate = wf.getframerate()
                raw_data = wf.readframes(wf.getnframes())

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
    n_frames = len(data) // (sampwidth * n_channels)
    fmt = {1: "B", 2: "h", 4: "i"}[sampwidth]
    samples = struct.unpack(f"<{n_frames * n_channels}{fmt}", data)
    mono = []
    for i in range(0, len(samples), n_channels):
        avg = sum(samples[i : i + n_channels]) // n_channels
        mono.append(avg)
    return struct.pack(f"<{len(mono)}{fmt}", *mono)


def _resample(data: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Resample 16-bit mono PCM via linear interpolation."""
    samples = array.array("h")
    samples.frombytes(data)
    n = len(samples)
    if n == 0:
        return data
    ratio = src_rate / dst_rate
    out_len = int(n / ratio)
    out = array.array("h", [0] * out_len)
    for i in range(out_len):
        pos = i * ratio
        idx = int(pos)
        frac = pos - idx
        if idx + 1 < n:
            out[i] = int(samples[idx] * (1 - frac) + samples[idx + 1] * frac)
        else:
            out[i] = samples[min(idx, n - 1)]
    return out.tobytes()
