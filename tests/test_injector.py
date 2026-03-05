"""Tests for text injector."""
import pytest
from unittest.mock import patch, MagicMock
from dictation.injector import TextInjector, detect_display_server


@patch("dictation.injector.subprocess.run")
@patch("dictation.injector.detect_display_server", return_value="x11")
def test_inject_text_x11(mock_detect, mock_run):
    injector = TextInjector()
    injector.type_text("hello world")
    mock_run.assert_called_once_with(
        ["xdotool", "type", "--clearmodifiers", "--", "hello world"],
        check=True,
    )


@patch("dictation.injector.subprocess.run")
@patch("dictation.injector.detect_display_server", return_value="wayland")
def test_inject_text_wayland(mock_detect, mock_run):
    injector = TextInjector()
    injector.type_text("hello world")
    mock_run.assert_called_once_with(
        ["wtype", "--", "hello world"],
        check=True,
    )


@patch("dictation.injector.subprocess.run")
@patch("dictation.injector.detect_display_server", return_value="x11")
def test_inject_backspaces(mock_detect, mock_run):
    injector = TextInjector()
    injector.backspace(5)
    mock_run.assert_called_once_with(
        ["xdotool", "key", "--clearmodifiers"] + ["BackSpace"] * 5,
        check=True,
    )


@patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11"})
def test_detect_display_server_x11():
    assert detect_display_server() == "x11"


@patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"})
def test_detect_display_server_wayland():
    assert detect_display_server() == "wayland"
