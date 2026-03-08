# Dictation

Lightweight local dictation service with real-time speech-to-text and text-to-speech. Runs entirely on CPU, no GPU required.

Uses [Vosk](https://alphacephei.com/vosk/) (Linux) or [Whisper](https://github.com/SYSTRAN/faster-whisper) (macOS) for STT and [Piper](https://github.com/rhasspy/piper) for neural TTS.

## Features

- **System-wide dictation** — press `Super+D` to toggle, text appears in the focused window
- **Real-time streaming** — words appear as you speak (not batch)
- **OpenAI-compatible API** — drop-in replacement for OpenAI audio endpoints on `localhost:5678`
- **Text-to-speech** — natural-sounding voices via Piper
- **CPU-only** — no GPU needed, runs on modest hardware
- **English by default** — other languages available via model swap

## Requirements

- Python 3.11+
- Linux (X11 or Wayland) or macOS
- PortAudio for audio capture/playback
- Linux: `xdotool` (X11) or `wtype` (Wayland) for text injection
- macOS: Accessibility permissions for hotkey and text injection

### System dependencies

```bash
# Debian/Ubuntu (X11)
sudo apt install xdotool libportaudio2

# Debian/Ubuntu (Wayland)
sudo apt install wtype libportaudio2

# macOS
brew install portaudio
```

> **macOS note:** On first run, macOS will prompt you to grant Accessibility permissions
> to your terminal (or the app running dictation) in **System Settings > Privacy & Security > Accessibility**.
> This is required for global hotkey detection and text injection.

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

### API (OpenAI-compatible)

While the daemon is running:

```bash
# Status
curl http://localhost:5678/status

# Text-to-speech (POST /v1/audio/speech)
curl -X POST http://localhost:5678/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model": "piper", "input": "Hello world", "voice": "alloy"}' \
  --output hello.wav

# Speech-to-text from file (POST /v1/audio/transcriptions)
curl -X POST http://localhost:5678/v1/audio/transcriptions \
  -F file=@audio.wav \
  -F model=whisper-1

# Stop active listening session
curl -X POST http://localhost:5678/stop
```

Real-time streaming transcription via WebSocket: `ws://localhost:5678/v1/realtime?intent=transcription`

## Configuration

Create the config file at the platform-appropriate location:

- **Linux:** `~/.config/dictation/config.toml`
- **macOS:** `~/Library/Application Support/dictation/config.toml`

```toml
[general]
hotkey = "super+d"
api_port = 5678

[stt]
engine = "vosk"              # "vosk" (Linux default) or "whisper" (macOS default)
model = "vosk-model-small-en-us-0.15"
language = "en"
whisper_model = "tiny"       # tiny, base, small, medium, large-v3

[tts]
voice = "en_US-lessac-medium"
```

## Autostart

### Linux (systemd)

```bash
cp contrib/dictation.service ~/.config/systemd/user/
systemctl --user enable --now dictation
```

### macOS (launchd)

```bash
cp contrib/com.dictation.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.dictation.plist
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

Tests cover: status endpoint, real TTS synthesis, batch transcription, realtime WebSocket STT, full TTS→STT round-trip, and CLI status.

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
curl -s -X POST http://localhost:5678/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"model": "piper", "input": "Hello world, this is a test.", "voice": "alloy"}' \
  -o /tmp/hello.wav

# Play it
aplay /tmp/hello.wav        # ALSA
# or: ffplay -nodisp /tmp/hello.wav

# Transcribe an audio file
curl -X POST http://localhost:5678/v1/audio/transcriptions \
  -F file=@/tmp/hello.wav \
  -F model=whisper-1
```

## Architecture

```
dictation start
  └─ DictationDaemon
       ├─ Vosk/Whisper STT (speech recognition)
       ├─ Piper TTS (on-demand synthesis)
       ├─ FastAPI (OpenAI-compatible REST + WebSocket on localhost:5678)
       ├─ pynput (global hotkey listener)
       └─ xdotool/wtype/AppleScript (text injection into focused window)
```
