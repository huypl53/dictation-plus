"""Tests for Whisper STT engine."""
import sys
import pytest
from unittest.mock import MagicMock, patch

# Mock faster_whisper before import
if "faster_whisper" not in sys.modules:
    sys.modules["faster_whisper"] = MagicMock()

from dictation.stt_whisper import WhisperSTTEngine, _RETRANSCRIBE_BYTES


@patch("dictation.stt_whisper.WhisperModel")
def test_whisper_engine_init(mock_model_cls):
    engine = WhisperSTTEngine(model_size="tiny")
    mock_model_cls.assert_called_once_with("tiny", compute_type="int8")
    assert engine.sample_rate == 16000


@patch("dictation.stt_whisper.WhisperModel")
def test_whisper_process_audio_accumulates(mock_model_cls):
    engine = WhisperSTTEngine(model_size="tiny")
    # Small chunk should accumulate without transcribing
    result = engine.process_audio(b"\x00" * 100)
    assert result.text == ""
    assert result.is_final is False


@patch("dictation.stt_whisper.WhisperModel")
def test_whisper_process_audio_transcribes_on_threshold(mock_model_cls):
    engine = WhisperSTTEngine(model_size="tiny")
    mock_model = mock_model_cls.return_value

    segment = MagicMock()
    segment.text = " hello world "
    mock_model.transcribe.return_value = ([segment], None)

    # Feed enough data to trigger transcription
    result = engine.process_audio(b"\x00" * _RETRANSCRIBE_BYTES)
    assert result.text == "hello world"
    assert result.is_final is False


@patch("dictation.stt_whisper.WhisperModel")
def test_whisper_finalize(mock_model_cls):
    engine = WhisperSTTEngine(model_size="tiny")
    mock_model = mock_model_cls.return_value

    segment = MagicMock()
    segment.text = " final text "
    mock_model.transcribe.return_value = ([segment], None)

    engine.process_audio(b"\x00" * 100)
    result = engine.finalize()
    assert result.text == "final text"
    assert result.is_final is True


@patch("dictation.stt_whisper.WhisperModel")
def test_whisper_finalize_empty(mock_model_cls):
    engine = WhisperSTTEngine(model_size="tiny")
    result = engine.finalize()
    assert result.text == ""
    assert result.is_final is True


@patch("dictation.stt_whisper.WhisperModel")
def test_whisper_reset(mock_model_cls):
    engine = WhisperSTTEngine(model_size="tiny")
    engine.process_audio(b"\x00" * 100)
    engine.reset()
    # Buffer should be cleared after reset
    result = engine.finalize()
    assert result.text == ""
