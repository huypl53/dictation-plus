"""CLI entry point for the dictation service."""
from __future__ import annotations

import argparse
import base64
import json
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
        resp = httpx.post(f"{base_url}/stop")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("text"):
                print(f"Dictation stopped. Final text: {data['text']}")
            else:
                print("Dictation stopped.")
        else:
            print(f"Error: {resp.status_code}", file=sys.stderr)
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
        resp = httpx.post(
            f"{base_url}/v1/audio/speech",
            json={"model": "piper", "input": text, "voice": "alloy"},
        )
        if resp.status_code == 200:
            import io
            import wave
            from dictation.audio import AudioPlayback
            with wave.open(io.BytesIO(resp.content), "rb") as wf:
                pcm_data = wf.readframes(wf.getnframes())
            playback = AudioPlayback()
            playback.play_raw(pcm_data)
        else:
            print(f"Error: {resp.status_code}", file=sys.stderr)
    except httpx.ConnectError:
        print("Daemon is not running.", file=sys.stderr)
        sys.exit(1)


def _cmd_listen(base_url: str, save_audio: str | None = None):
    try:
        import websockets.sync.client as ws_client
        from websockets.exceptions import InvalidURI, WebSocketException
        from dictation.audio import AudioCapture

        capture = AudioCapture(sample_rate=16000)
        capture.start()

        audio_chunks: list[bytes] = []

        # Connect to OpenAI-compatible realtime WebSocket
        ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/v1/realtime?intent=transcription"

        print("Listening... Press Ctrl+C to stop.")
        try:
            ws = ws_client.connect(ws_url)
        except (OSError, WebSocketException) as exc:
            capture.stop()
            print("Daemon is not running.", file=sys.stderr)
            sys.exit(1)

        with ws:
            # Receive session.created
            msg = json.loads(ws.recv())
            assert msg["type"] == "session.created"

            try:
                while True:
                    data = capture.read(timeout=0.5)
                    if data:
                        if save_audio:
                            audio_chunks.append(data)
                        # Send audio as base64 via OpenAI protocol
                        ws.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": base64.b64encode(data).decode(),
                        }))
                        # Check for transcription deltas
                        try:
                            ws.settimeout(0.1)
                            result = json.loads(ws.recv())
                            if result["type"] == "conversation.item.input_audio_transcription.delta":
                                print(f"... {result['delta']}", end="\r")
                            elif result["type"] == "conversation.item.input_audio_transcription.completed":
                                print(result["transcript"])
                        except TimeoutError:
                            pass
            except KeyboardInterrupt:
                # Commit buffer to get final transcription
                ws.settimeout(5.0)
                ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
                while True:
                    result = json.loads(ws.recv())
                    if result["type"] == "conversation.item.input_audio_transcription.completed":
                        if result["transcript"]:
                            print(result["transcript"])
                        break
            finally:
                capture.stop()
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
