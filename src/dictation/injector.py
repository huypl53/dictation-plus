"""Type text into the focused window using xdotool or wtype."""
from __future__ import annotations

import os
import subprocess


def detect_display_server() -> str:
    """Detect whether running on X11 or Wayland."""
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if "wayland" in session_type:
        return "wayland"
    return "x11"


class TextInjector:
    """Types text into the currently focused window."""

    def __init__(self):
        self._display = detect_display_server()

    def type_text(self, text: str) -> None:
        """Type text into the focused window."""
        if not text:
            return
        if self._display == "wayland":
            subprocess.run(["wtype", "--", text], check=True)
        else:
            subprocess.run(
                ["xdotool", "type", "--clearmodifiers", "--", text],
                check=True,
            )

    def backspace(self, count: int) -> None:
        """Send backspace keys to delete characters."""
        if count <= 0:
            return
        if self._display == "wayland":
            subprocess.run(
                ["wtype", "-k"] + ["BackSpace"] * count,
                check=True,
            )
        else:
            subprocess.run(
                ["xdotool", "key", "--clearmodifiers"] + ["BackSpace"] * count,
                check=True,
            )
