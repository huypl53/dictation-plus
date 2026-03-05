"""Integration smoke test — verifies modules wire together."""
import pytest
from unittest.mock import patch, MagicMock
from dictation.config import DictationConfig
from dictation.daemon import DictationDaemon


@patch("dictation.daemon.AudioCapture")
@patch("dictation.daemon.STTEngine")
@patch("dictation.daemon.TextInjector")
def test_daemon_creates_with_config(mock_inj, mock_stt, mock_cap):
    config = DictationConfig(api_port=9999, hotkey="ctrl+d")

    with patch("dictation.daemon.ModelManager") as mock_mgr_cls:
        mock_mgr = mock_mgr_cls.return_value
        mock_mgr.is_vosk_model_available.return_value = True
        mock_mgr.vosk_model_path.return_value = "/fake/model"

        daemon = DictationDaemon(config=config)
        assert daemon._config.api_port == 9999
        assert daemon.is_listening is False
