"""Tests for STT engine."""
import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from dictation.stt import STTEngine, STTResult


def test_stt_result_dataclass():
    result = STTResult(text="hello", is_final=True)
    assert result.text == "hello"
    assert result.is_final is True


def test_stt_result_partial():
    result = STTResult(text="hel", is_final=False)
    assert result.is_final is False


@patch("dictation.stt.KaldiRecognizer")
@patch("dictation.stt.Model")
def test_stt_engine_init(mock_model_cls, mock_rec_cls):
    engine = STTEngine(model_path="/fake/model")
    mock_model_cls.assert_called_once_with(model_path="/fake/model")
    assert engine.sample_rate == 16000


@patch("dictation.stt.KaldiRecognizer")
@patch("dictation.stt.Model")
def test_stt_engine_process_audio_partial(mock_model_cls, mock_rec_cls):
    engine = STTEngine(model_path="/fake/model")
    mock_rec = mock_rec_cls.return_value
    mock_rec.AcceptWaveform.return_value = 0
    mock_rec.PartialResult.return_value = json.dumps({"partial": "hello"})

    result = engine.process_audio(b"\x00" * 100)
    assert result.text == "hello"
    assert result.is_final is False


@patch("dictation.stt.KaldiRecognizer")
@patch("dictation.stt.Model")
def test_stt_engine_process_audio_final(mock_model_cls, mock_rec_cls):
    engine = STTEngine(model_path="/fake/model")
    mock_rec = mock_rec_cls.return_value
    mock_rec.AcceptWaveform.return_value = 1
    mock_rec.Result.return_value = json.dumps({"text": "hello world"})

    result = engine.process_audio(b"\x00" * 100)
    assert result.text == "hello world"
    assert result.is_final is True


@patch("dictation.stt.KaldiRecognizer")
@patch("dictation.stt.Model")
def test_stt_engine_reset(mock_model_cls, mock_rec_cls):
    engine = STTEngine(model_path="/fake/model")
    engine.reset()
    # After reset, a new recognizer should be created
    assert mock_rec_cls.call_count == 2


@patch("dictation.stt.KaldiRecognizer")
@patch("dictation.stt.Model")
def test_stt_engine_finalize(mock_model_cls, mock_rec_cls):
    engine = STTEngine(model_path="/fake/model")
    with patch.object(engine, "_recognizer") as mock_rec:
        mock_rec.FinalResult.return_value = json.dumps({"text": "final text"})
        result = engine.finalize()
        assert result.text == "final text"
        assert result.is_final is True
