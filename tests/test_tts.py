"""Tests for TTS engine."""
import io
import wave
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from dictation.tts import TTSEngine


@patch("dictation.tts.PiperVoice")
def test_tts_engine_init(mock_piper_cls):
    engine = TTSEngine(model_path="/fake/model.onnx")
    mock_piper_cls.load.assert_called_once_with("/fake/model.onnx")


@patch("dictation.tts.PiperVoice")
def test_tts_synthesize_wav_bytes(mock_piper_cls):
    mock_voice = MagicMock()
    mock_piper_cls.load.return_value = mock_voice

    # Mock synthesize_wav to write valid WAV data
    def fake_synthesize_wav(text, wav_file, **kwargs):
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\x00" * 100)

    mock_voice.synthesize_wav.side_effect = fake_synthesize_wav

    engine = TTSEngine(model_path="/fake/model.onnx")
    wav_bytes = engine.synthesize(text="hello")
    assert len(wav_bytes) > 0
    # Verify it's valid WAV
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2


@patch("dictation.tts.PiperVoice")
def test_tts_synthesize_to_file(mock_piper_cls, tmp_path):
    mock_voice = MagicMock()
    mock_piper_cls.load.return_value = mock_voice

    def fake_synthesize_wav(text, wav_file, **kwargs):
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\x00" * 100)

    mock_voice.synthesize_wav.side_effect = fake_synthesize_wav

    engine = TTSEngine(model_path="/fake/model.onnx")
    out_path = tmp_path / "output.wav"
    engine.synthesize_to_file("hello", out_path)
    assert out_path.exists()
    assert out_path.stat().st_size > 0
