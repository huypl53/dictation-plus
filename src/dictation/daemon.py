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
            if result.text:
                if self._last_partial:
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
