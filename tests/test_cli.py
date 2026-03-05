"""Tests for CLI."""
import pytest
from unittest.mock import patch, MagicMock
from dictation.cli import main, parse_args


def test_parse_args_start():
    args = parse_args(["start"])
    assert args.command == "start"


def test_parse_args_stop():
    args = parse_args(["stop"])
    assert args.command == "stop"


def test_parse_args_say():
    args = parse_args(["say", "hello world"])
    assert args.command == "say"
    assert args.text == "hello world"


def test_parse_args_listen():
    args = parse_args(["listen"])
    assert args.command == "listen"


def test_parse_args_status():
    args = parse_args(["status"])
    assert args.command == "status"


@patch("dictation.cli.httpx")
def test_status_command(mock_httpx):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "running", "listening": False}
    mock_resp.status_code = 200
    mock_httpx.get.return_value = mock_resp

    with patch("sys.argv", ["dictation", "status"]):
        # Should not raise
        main()
