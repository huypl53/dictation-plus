"""Configuration management."""
from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


def _default_data_dir() -> Path:
    """Return platform-appropriate data directory."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "dictation"
    return Path.home() / ".local" / "share" / "dictation"


def _default_config_path() -> Path:
    """Return platform-appropriate config file path."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "dictation" / "config.toml"
    return Path.home() / ".config" / "dictation" / "config.toml"


def _default_stt_engine() -> str:
    """Return default STT engine for the current platform."""
    if sys.platform == "darwin":
        return "whisper"
    return "vosk"


@dataclass
class DictationConfig:
    hotkey: str = "super+d"
    api_port: int = 5678
    stt_engine: str = field(default_factory=_default_stt_engine)
    stt_model: str = "vosk-model-small-en-us-0.15"
    stt_language: str = "en"
    whisper_model: str = "tiny"
    tts_voice: str = "en_US-lessac-medium"
    models_dir: Path = field(
        default_factory=lambda: _default_data_dir() / "models"
    )


DEFAULT_CONFIG = DictationConfig()

DEFAULT_CONFIG_PATH = _default_config_path()


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
        stt_engine=stt.get("engine", DEFAULT_CONFIG.stt_engine),
        stt_model=stt.get("model", DEFAULT_CONFIG.stt_model),
        stt_language=stt.get("language", DEFAULT_CONFIG.stt_language),
        whisper_model=stt.get("whisper_model", DEFAULT_CONFIG.whisper_model),
        tts_voice=tts.get("voice", DEFAULT_CONFIG.tts_voice),
        models_dir=Path(general.get("models_dir", str(DEFAULT_CONFIG.models_dir))),
    )
