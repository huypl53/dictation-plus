"""FastAPI service for dictation."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
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
        if state.tts_engine is None:
            raise HTTPException(status_code=503, detail="TTS engine not available")
        wav_bytes = state.tts_engine.synthesize(req.text)
        return Response(content=wav_bytes, media_type="audio/wav")

    @app.post("/stt/start")
    async def stt_start(request: Request):
        if state.stt_engine is None:
            raise HTTPException(status_code=503, detail="STT engine not available")
        state.is_listening = True
        host = request.headers.get("host", "localhost")
        return {"status": "listening", "ws_url": f"ws://{host}/ws/stt"}

    @app.post("/stt/stop")
    async def stt_stop():
        if state.stt_engine is None:
            raise HTTPException(status_code=503, detail="STT engine not available")
        state.is_listening = False
        result = state.stt_engine.finalize()
        return {"text": result.text, "is_final": result.is_final}

    @app.websocket("/ws/stt")
    async def ws_stt(websocket: WebSocket):
        if state.stt_engine is None:
            await websocket.close(code=1013, reason="STT engine not available")
            return
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
