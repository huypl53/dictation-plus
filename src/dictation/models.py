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
