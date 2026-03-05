"""Configuration management."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DictationConfig:
    hotkey: str = "super+d"
    api_port: int = 5678
    stt_model: str = "vosk-model-small-en-us-0.15"
    stt_language: str = "en"
    tts_voice: str = "en_US-lessac-medium"
    models_dir: Path = field(
        default_factory=lambda: Path.home() / ".local" / "share" / "dictation" / "models"
    )


DEFAULT_CONFIG = DictationConfig()

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "dictation" / "config.toml"


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
        stt_model=stt.get("model", DEFAULT_CONFIG.stt_model),
        stt_language=stt.get("language", DEFAULT_CONFIG.stt_language),
        tts_voice=tts.get("voice", DEFAULT_CONFIG.tts_voice),
        models_dir=Path(general.get("models_dir", str(DEFAULT_CONFIG.models_dir))),
    )
