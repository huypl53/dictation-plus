"""Tests for model management."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from dictation.models import ModelManager


def test_model_manager_default_dir():
    mgr = ModelManager()
    assert mgr.models_dir == Path.home() / ".local" / "share" / "dictation" / "models"


def test_model_manager_custom_dir(tmp_path):
    mgr = ModelManager(models_dir=tmp_path)
    assert mgr.models_dir == tmp_path


def test_vosk_model_path(tmp_path):
    mgr = ModelManager(models_dir=tmp_path)
    path = mgr.vosk_model_path("vosk-model-small-en-us-0.15")
    assert path == tmp_path / "vosk" / "vosk-model-small-en-us-0.15"


def test_piper_model_path(tmp_path):
    mgr = ModelManager(models_dir=tmp_path)
    path = mgr.piper_model_path("en_US-lessac-medium")
    assert path == tmp_path / "piper" / "en_US-lessac-medium.onnx"


def test_vosk_model_available(tmp_path):
    mgr = ModelManager(models_dir=tmp_path)
    # Not downloaded yet
    assert mgr.is_vosk_model_available("vosk-model-small-en-us-0.15") is False
    # Create the directory
    model_dir = tmp_path / "vosk" / "vosk-model-small-en-us-0.15"
    model_dir.mkdir(parents=True)
    assert mgr.is_vosk_model_available("vosk-model-small-en-us-0.15") is True


def test_piper_model_available(tmp_path):
    mgr = ModelManager(models_dir=tmp_path)
    assert mgr.is_piper_model_available("en_US-lessac-medium") is False
    model_file = tmp_path / "piper" / "en_US-lessac-medium.onnx"
    model_file.parent.mkdir(parents=True)
    model_file.touch()
    (tmp_path / "piper" / "en_US-lessac-medium.onnx.json").touch()
    assert mgr.is_piper_model_available("en_US-lessac-medium") is True
