"""Shared test fixtures."""
import sys
from unittest.mock import MagicMock

# Mock sounddevice before any test module imports it,
# since it requires PortAudio at import time.
if "sounddevice" not in sys.modules:
    sys.modules["sounddevice"] = MagicMock()

# Mock vosk on platforms where it's not available (e.g. macOS).
if "vosk" not in sys.modules:
    sys.modules["vosk"] = MagicMock()

# Mock faster_whisper on platforms where it's not available (e.g. Linux CI).
if "faster_whisper" not in sys.modules:
    sys.modules["faster_whisper"] = MagicMock()
