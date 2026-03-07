"""Tests for text injector."""
import pytest
from unittest.mock import patch, MagicMock
from dictation.injector import TextInjector, detect_display_server, _escape_applescript


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
@patch("dictation.injector.detect_display_server", return_value="macos")
def test_inject_text_macos(mock_detect, mock_run):
    injector = TextInjector()
    injector.type_text("hello world")
    mock_run.assert_called_once_with(
        ["osascript", "-e",
         'tell application "System Events" to keystroke "hello world"'],
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


@patch("dictation.injector.subprocess.run")
@patch("dictation.injector.detect_display_server", return_value="macos")
def test_inject_backspaces_macos(mock_detect, mock_run):
    injector = TextInjector()
    injector.backspace(3)
    assert mock_run.call_count == 3
    mock_run.assert_called_with(
        ["osascript", "-e",
         'tell application "System Events" to key code 51'],
        check=True,
    )


@patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11"})
@patch("dictation.injector.sys")
def test_detect_display_server_x11(mock_sys):
    mock_sys.platform = "linux"
    assert detect_display_server() == "x11"


@patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"})
@patch("dictation.injector.sys")
def test_detect_display_server_wayland(mock_sys):
    mock_sys.platform = "linux"
    assert detect_display_server() == "wayland"


@patch("dictation.injector.sys")
def test_detect_display_server_macos(mock_sys):
    mock_sys.platform = "darwin"
    assert detect_display_server() == "macos"


def test_escape_applescript():
    assert _escape_applescript('say "hi"') == 'say \\"hi\\"'
    assert _escape_applescript("back\\slash") == "back\\\\slash"
