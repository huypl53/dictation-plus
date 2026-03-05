"""Tests for the dictation daemon."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from dictation.daemon import DictationDaemon


@patch("dictation.daemon.AudioCapture")
@patch("dictation.daemon.STTEngine")
@patch("dictation.daemon.TextInjector")
def test_daemon_toggle_on(mock_injector_cls, mock_stt_cls, mock_capture_cls):
    daemon = DictationDaemon.__new__(DictationDaemon)
    daemon._stt = mock_stt_cls.return_value
    daemon._capture = mock_capture_cls.return_value
    daemon._injector = mock_injector_cls.return_value
    daemon._is_listening = False
    daemon._last_partial = ""

    daemon.toggle_dictation()
    assert daemon._is_listening is True
    daemon._capture.start.assert_called_once()


@patch("dictation.daemon.AudioCapture")
@patch("dictation.daemon.STTEngine")
@patch("dictation.daemon.TextInjector")
def test_daemon_toggle_off(mock_injector_cls, mock_stt_cls, mock_capture_cls):
    daemon = DictationDaemon.__new__(DictationDaemon)
    daemon._stt = mock_stt_cls.return_value
    daemon._stt.finalize.return_value = MagicMock(text="final", is_final=True)
    daemon._capture = mock_capture_cls.return_value
    daemon._injector = mock_injector_cls.return_value
    daemon._is_listening = True
    daemon._last_partial = "part"

    daemon.toggle_dictation()
    assert daemon._is_listening is False
    daemon._capture.stop.assert_called_once()
