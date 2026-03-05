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
