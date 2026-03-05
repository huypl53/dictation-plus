"""Tests for configuration loading."""
import pytest
from pathlib import Path
from dictation.config import DictationConfig, load_config, DEFAULT_CONFIG


def test_default_config_values():
    config = DictationConfig()
    assert config.hotkey == "super+d"
    assert config.api_port == 5678
    assert config.stt_model == "vosk-model-small-en-us-0.15"
    assert config.stt_language == "en"
    assert config.tts_voice == "en_US-lessac-medium"
    assert config.models_dir == Path.home() / ".local" / "share" / "dictation" / "models"


def test_load_config_from_toml(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        '[general]\nhotkey = "ctrl+shift+d"\napi_port = 9999\n'
        '[stt]\nmodel = "vosk-model-en-us-0.22"\n'
        '[tts]\nvoice = "en_US-amy-low"\n'
    )
    config = load_config(config_file)
    assert config.hotkey == "ctrl+shift+d"
    assert config.api_port == 9999
    assert config.stt_model == "vosk-model-en-us-0.22"
    assert config.tts_voice == "en_US-amy-low"


def test_load_config_missing_file_returns_defaults():
    config = load_config(Path("/nonexistent/config.toml"))
    assert config.hotkey == "super+d"


def test_load_config_partial_override(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text('[general]\napi_port = 7777\n')
    config = load_config(config_file)
    assert config.api_port == 7777
    assert config.hotkey == "super+d"  # default preserved
