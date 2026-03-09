"""Dictation daemon — ties STT, TTS, audio, hotkey, and API together."""
from __future__ import annotations

import io
import logging
import threading
import wave

from dictation.audio import AudioCapture, AudioPlayback
from dictation.config import DictationConfig, load_config
from dictation.injector import TextInjector
from dictation.models import ModelManager
from dictation.stt import STTEngine, STTResult

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

    def _ensure_stt(self):
        if self._stt is None:
            engine = self._config.stt_engine
            if engine == "whisper":
                from dictation.stt_whisper import WhisperSTTEngine
                logger.info("Using Whisper STT (model: %s)", self._config.whisper_model)
                self._stt = WhisperSTTEngine(model_size=self._config.whisper_model)
            else:
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
            if result.text:
                if self._last_partial:
                    self._injector.backspace(len(self._last_partial))
                self._injector.type_text(result.text)
        self._last_partial = ""
        logger.info("Dictation stopped")

    def stop_listening(self) -> str:
        """Stop dictation and return the final transcribed text (DaemonControl protocol)."""
        if not self._is_listening:
            return ""
        self._is_listening = False
        self._capture.stop()
        text: str = ""
        if self._stt:
            result: STTResult = self._stt.finalize()
            text = result.text
            if text:
                if self._last_partial:
                    self._injector.backspace(len(self._last_partial))
                self._injector.type_text(text)
        self._last_partial = ""
        logger.info("Dictation stopped via API")
        return text

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
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            pcm_data: bytes = wf.readframes(wf.getnframes())
        self._playback.play_raw(pcm_data)

    def _ensure_models_downloaded(self) -> None:
        """Download models if needed, without instantiating engines."""
        engine = self._config.stt_engine
        if engine == "whisper":
            pass  # Whisper downloads on first use internally
        else:
            if not self._model_mgr.is_vosk_model_available(self._config.stt_model):
                logger.info("Downloading Vosk model: %s", self._config.stt_model)
                self._model_mgr.download_vosk_model(self._config.stt_model)
        if not self._model_mgr.is_piper_model_available(self._config.tts_voice):
            logger.info("Downloading Piper voice: %s", self._config.tts_voice)
            self._model_mgr.download_piper_voice(self._config.tts_voice)

    def _create_stt_engine(self):
        """Create a new STT engine instance (for pool factory use)."""
        engine = self._config.stt_engine
        if engine == "whisper":
            from dictation.stt_whisper import WhisperSTTEngine
            return WhisperSTTEngine(model_size=self._config.whisper_model)
        else:
            model_path = self._model_mgr.vosk_model_path(self._config.stt_model)
            if not self._model_mgr.is_vosk_model_available(self._config.stt_model):
                self._model_mgr.download_vosk_model(self._config.stt_model)
            return STTEngine(model_path=str(model_path))

    def _create_tts_engine(self):
        """Create a new TTS engine instance (for pool factory use)."""
        from dictation.tts import TTSEngine
        model_path = self._model_mgr.piper_model_path(self._config.tts_voice)
        if not self._model_mgr.is_piper_model_available(self._config.tts_voice):
            self._model_mgr.download_piper_voice(self._config.tts_voice)
        return TTSEngine(model_path=model_path)

    def run(self) -> None:
        """Run the daemon with hotkey listener and API server."""
        import uvicorn
        from pynput import keyboard
        from dictation.api import create_app
        from dictation.pool import EnginePool

        # Download models eagerly (but don't instantiate engines yet — pools create on demand)
        self._ensure_models_downloaded()

        stt_pool = EnginePool(
            self._create_stt_engine, max_size=2, on_release=lambda e: e.reset()
        )
        tts_pool = EnginePool(self._create_tts_engine, max_size=2)
        app = create_app(stt_pool=stt_pool, tts_pool=tts_pool, daemon=self)

        # Parse hotkey — convert "super+d" to "<cmd>+d"
        hotkey_str = self._config.hotkey.replace("super", "<cmd>")
        hotkey = keyboard.HotKey(
            keyboard.HotKey.parse(hotkey_str),
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
