"""Tests for audio capture and playback."""
import pytest
from unittest.mock import patch, MagicMock
from dictation.audio import AudioCapture, AudioPlayback


@patch("dictation.audio.sd")
def test_audio_capture_start_stop(mock_sd):
    mock_stream = MagicMock()
    mock_sd.RawInputStream.return_value = mock_stream

    capture = AudioCapture(sample_rate=16000)
    capture.start()
    mock_stream.start.assert_called_once()

    capture.stop()
    mock_stream.stop.assert_called_once()
    mock_stream.close.assert_called_once()


@patch("dictation.audio.sd")
def test_audio_playback_play_bytes(mock_sd):
    playback = AudioPlayback()
    # 16-bit mono silence
    wav_data = b"\x00\x00" * 1000
    playback.play_raw(wav_data, sample_rate=22050)
    mock_sd.play.assert_called_once()
