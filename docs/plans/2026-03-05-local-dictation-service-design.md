# Local Dictation Service — Design

## Goal

A lightweight, local, CPU-only dictation service for Linux (macOS nice-to-have) providing real-time speech-to-text and text-to-speech. System-wide dictation via global hotkey plus a local REST/WebSocket API for programmatic access.

## Technology Choices

- **STT:** Vosk — true real-time streaming, ~40MB model, designed for CPU
- **TTS:** Piper — fast neural TTS on CPU, natural-sounding, ~100MB voice models
- **API:** FastAPI + uvicorn on `localhost:5678`
- **Language:** Python
- **Default language:** English

## Architecture

```
┌─────────────────────────────────────┐
│         System-wide Hotkey          │
│   (Super+D toggle via pynput)       │
├─────────────────────────────────────┤
│         Dictation Daemon            │
│  ┌───────────┐  ┌────────────────┐  │
│  │  Vosk STT │  │   Piper TTS    │  │
│  │ (streaming)│  │  (on-demand)   │  │
│  └───────────┘  └────────────────┘  │
├─────────────────────────────────────┤
│          FastAPI Service            │
│   REST + WebSocket (localhost)      │
├─────────────────────────────────────┤
│        Text Input Layer             │
│  xdotool (X11) / wtype (Wayland)   │
└─────────────────────────────────────┘
```

**Components:**

1. **Daemon process** — long-running background service managing mic input, Vosk model, and Piper
2. **FastAPI server** — local-only API on `localhost:5678`
3. **Hotkey listener** — global `Super+D` to toggle dictation on/off
4. **Text injector** — types recognized text into focused window via xdotool/wtype

## API Design

### REST Endpoints

- `POST /stt/start` — start listening, returns WebSocket URL
- `POST /stt/stop` — stop listening, returns final transcript
- `POST /tts` — `{"text": "hello", "voice": "en_US-amy"}` → WAV audio
- `GET /status` — service status
- `GET /voices` — list TTS voices
- `GET /models` — list STT models

### WebSocket

- `ws://localhost:5678/ws/stt` — real-time streaming STT
  - Partial: `{"text": "hello", "is_final": false}`
  - Final: `{"text": "hello world", "is_final": true}`

### CLI

- `dictation start` — start daemon
- `dictation stop` — stop daemon
- `dictation say "text"` — TTS, play through speakers
- `dictation listen` — one-shot STT, print to stdout
- `dictation status` — show service status

## Data Flow

### STT (dictation mode)

1. User presses `Super+D` → daemon captures mic via `sounddevice`
2. Audio chunks streamed to Vosk in real-time
3. Partial results typed into focused window
4. Final result replaces partial text
5. `Super+D` again → stops listening

### TTS

1. API call or CLI with text
2. Piper generates WAV
3. Audio played through default speakers via `sounddevice`

## Configuration

File: `~/.config/dictation/config.toml`

```toml
[general]
hotkey = "super+d"
api_port = 5678

[stt]
model = "vosk-model-small-en-us"
language = "en"

[tts]
voice = "en_US-amy-medium"
```

## Models & Storage

- Models stored in `~/.local/share/dictation/models/`
- Auto-download on first run with progress bar
- Vosk model: `vosk-model-small-en-us` (~40MB)
- Piper voice: `en_US-amy-medium` (~100MB)

## Dependencies

- `vosk` — STT engine
- `piper-tts` — TTS engine
- `fastapi` + `uvicorn` — API server
- `sounddevice` — audio capture/playback
- `pynput` — global hotkey
- `tomli` — config parsing

System: `xdotool` (X11) or `wtype` (Wayland)

## Error Handling

- No mic → TTS-only mode with clear message
- Model not found → auto-download
- Audio device busy → retry with backoff
- Hotkey conflict → fallback hotkey, log warning

## Packaging

- Python package with `pyproject.toml`
- Entry point: `dictation` CLI
- Optional systemd service file for auto-start
- Installable via `pip install -e .`

## Testing

- Unit tests for API endpoints (mocked audio)
- Integration test for STT with sample audio file
- TTS output validation (non-empty file generated)
