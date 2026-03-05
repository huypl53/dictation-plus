"""Shared test fixtures."""
import sys
from unittest.mock import MagicMock

# Mock sounddevice before any test module imports it,
# since it requires PortAudio at import time.
if "sounddevice" not in sys.modules:
    sys.modules["sounddevice"] = MagicMock()
