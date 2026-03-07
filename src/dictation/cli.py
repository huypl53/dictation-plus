"""CLI entry point for the dictation service."""
from __future__ import annotations

import argparse
import sys

import httpx

from dictation.config import load_config

DEFAULT_BASE_URL = "http://127.0.0.1:{port}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dictation",
        description="Lightweight local dictation service",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("start", help="Start the dictation daemon")
    sub.add_parser("stop", help="Stop the dictation daemon")
    sub.add_parser("status", help="Show service status")
    listen_parser = sub.add_parser("listen", help="One-shot STT, print transcript to stdout")
    listen_parser.add_argument("--save-audio", metavar="PATH", help="Save recorded audio to a WAV file for debugging")

    say_parser = sub.add_parser("say", help="Speak text aloud")
    say_parser.add_argument("text", help="Text to speak")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    config = load_config()
    base_url = DEFAULT_BASE_URL.format(port=config.api_port)

    if args.command == "start":
        _cmd_start(config)
    elif args.command == "stop":
        _cmd_stop(base_url)
    elif args.command == "status":
        _cmd_status(base_url)
    elif args.command == "say":
        _cmd_say(base_url, args.text)
    elif args.command == "listen":
        _cmd_listen(base_url, save_audio=getattr(args, "save_audio", None))


def _cmd_start(config):
    from dictation.daemon import DictationDaemon
    daemon = DictationDaemon(config=config)
    print(f"Starting dictation daemon on port {config.api_port}...")
    print(f"Hotkey: {config.hotkey}")
    daemon.run()


def _cmd_stop(base_url: str):
    try:
        resp = httpx.post(f"{base_url}/stt/stop")
        print("Dictation stopped.")
    except httpx.ConnectError:
        print("Daemon is not running.", file=sys.stderr)
        sys.exit(1)


def _cmd_status(base_url: str):
    try:
        resp = httpx.get(f"{base_url}/status")
        data = resp.json()
        print(f"Status: {data['status']}")
        print(f"Listening: {data['listening']}")
        print(f"STT available: {data.get('stt_available', False)}")
        print(f"TTS available: {data.get('tts_available', False)}")
    except httpx.ConnectError:
        print("Daemon is not running.", file=sys.stderr)
        sys.exit(1)


def _cmd_say(base_url: str, text: str):
    try:
        resp = httpx.post(f"{base_url}/tts", json={"text": text})
        if resp.status_code == 200:
            from dictation.audio import AudioPlayback
            playback = AudioPlayback()
            playback.play_raw(resp.content[44:])  # skip WAV header
        else:
            print(f"Error: {resp.status_code}", file=sys.stderr)
    except httpx.ConnectError:
        print("Daemon is not running.", file=sys.stderr)
        sys.exit(1)


def _cmd_listen(base_url: str, save_audio: str | None = None):
    try:
        import json
        import websockets.sync.client as ws_client
        resp = httpx.post(f"{base_url}/stt/start")
        ws_url = resp.json()["ws_url"]

        from dictation.audio import AudioCapture
        capture = AudioCapture(sample_rate=16000)
        capture.start()

        audio_chunks: list[bytes] = []

        print("Listening... Press Ctrl+C to stop.")
        with ws_client.connect(ws_url) as ws:
            try:
                while True:
                    data = capture.read(timeout=0.5)
                    if data:
                        if save_audio:
                            audio_chunks.append(data)
                        ws.send(data)
                        result = ws.recv()
                        parsed = json.loads(result)
                        if parsed.get("is_final"):
                            print(parsed["text"])
                        else:
                            print(f"... {parsed['text']}", end="\r")
            except KeyboardInterrupt:
                pass
            finally:
                capture.stop()
                httpx.post(f"{base_url}/stt/stop")
                if save_audio and audio_chunks:
                    _save_debug_audio(save_audio, b"".join(audio_chunks))
                print("\nDone.")
    except httpx.ConnectError:
        print("Daemon is not running.", file=sys.stderr)
        sys.exit(1)


def _save_debug_audio(path: str, raw_pcm: bytes) -> None:
    """Save raw PCM audio to a WAV file for debugging."""
    import wave
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(raw_pcm)
    print(f"Audio saved to {path}")
