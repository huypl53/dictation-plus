# Dictation

Lightweight local dictation service with real-time speech-to-text and text-to-speech. Runs entirely on CPU, no GPU required.

Uses [Vosk](https://alphacephei.com/vosk/) for streaming STT and [Piper](https://github.com/rhasspy/piper) for neural TTS.

## Features

- **System-wide dictation** — press `Super+D` to toggle, text appears in the focused window
- **Real-time streaming** — words appear as you speak (not batch)
- **Local REST/WebSocket API** — integrate with other apps via `localhost:5678`
- **Text-to-speech** — natural-sounding voices via Piper
- **CPU-only** — no GPU needed, runs on modest hardware
- **English by default** — other languages available via model swap

## Requirements

- Python 3.11+
- Linux (X11 or Wayland)
- `xdotool` (X11) or `wtype` (Wayland) for system-wide typing
- PortAudio (`libportaudio2`) for audio capture/playback

### System dependencies

```bash
# Debian/Ubuntu
sudo apt install xdotool libportaudio2

# Wayland
sudo apt install wtype libportaudio2
```

## Install

```bash
git clone <repo-url> && cd dictation
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Models are downloaded automatically on first run (~140MB total).

## Usage

### Start the daemon

```bash
dictation start
```

Press `Super+D` to toggle dictation on/off. Speak and text appears in the focused window.

### CLI commands

```bash
dictation start       # Start the daemon
dictation stop        # Stop listening
dictation status      # Show service status
dictation say "text"  # Speak text aloud
dictation listen      # One-shot STT, prints to stdout
```

### API

While the daemon is running:

```bash
# Status
curl http://localhost:5678/status

# Text-to-speech
curl -X POST http://localhost:5678/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world"}' \
  --output hello.wav

# Start/stop listening
curl -X POST http://localhost:5678/stt/start
curl -X POST http://localhost:5678/stt/stop
```

WebSocket for real-time streaming: `ws://localhost:5678/ws/stt`

## Configuration

Create `~/.config/dictation/config.toml`:

```toml
[general]
hotkey = "super+d"
api_port = 5678

[stt]
model = "vosk-model-small-en-us-0.15"
language = "en"

[tts]
voice = "en_US-lessac-medium"
```

## Autostart (systemd)

```bash
cp contrib/dictation.service ~/.config/systemd/user/
systemctl --user enable --now dictation
```

## Development

```bash
source .venv/bin/activate
python -m pytest -v
```

### E2E tests (Docker)

Runs real Vosk STT and Piper TTS engines in an Ubuntu container — no models or dependencies needed on the host, just Docker.

```bash
# Run all 5 E2E tests
bash tests/e2e/run_e2e.sh
```

Tests cover: status endpoint, real TTS synthesis, WebSocket STT, full TTS→STT round-trip, and CLI status.

### Live demo (Docker)

Start the full API server in Docker, exposed on your host:

```bash
# Start on default port 5678 (or pass a custom port)
bash tests/e2e/demo.sh
bash tests/e2e/demo.sh 9999   # custom port
```

Then from another terminal:

```bash
# Check status
curl http://localhost:5678/status

# Generate speech → save WAV
curl -s -X POST http://localhost:5678/tts \
  -H 'Content-Type: application/json' \
  -d '{"text": "Hello world, this is a test."}' \
  -o /tmp/hello.wav

# Play it
aplay /tmp/hello.wav        # ALSA
# or: ffplay -nodisp /tmp/hello.wav

# Stream STT via WebSocket (using websocat)
arecord -f S16_LE -r 16000 -c 1 -t raw | \
  websocat ws://localhost:5678/ws/stt --binary
```

## Architecture

```
dictation start
  └─ DictationDaemon
       ├─ Vosk STT (streaming recognition)
       ├─ Piper TTS (on-demand synthesis)
       ├─ FastAPI (REST + WebSocket on localhost:5678)
       ├─ pynput (global hotkey listener)
       └─ xdotool/wtype (text injection into focused window)
```
