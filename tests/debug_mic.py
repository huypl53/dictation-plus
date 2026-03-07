#!/usr/bin/env python3
"""Quick mic diagnostic — records 3 seconds and reports audio levels."""
import sys
import wave
import numpy as np
import sounddevice as sd

RATE = 16000
DURATION = 3

print(f"Default input device: {sd.query_devices(kind='input')}")
print(f"\nRecording {DURATION}s at {RATE}Hz... speak now!")

audio = sd.rec(int(DURATION * RATE), samplerate=RATE, channels=1, dtype="int16")
sd.wait()

peak = np.max(np.abs(audio))
rms = np.sqrt(np.mean(audio.astype(np.float32) ** 2))

print(f"\nPeak amplitude: {peak}  (max possible: 32767)")
print(f"RMS amplitude:  {rms:.1f}")

if peak < 100:
    print("\n⚠ Audio is essentially silent.")
    print("  → macOS may not have granted microphone access to this terminal.")
    print("  → Check: System Settings > Privacy & Security > Microphone")
    print(f"  → Ensure your terminal app is listed and enabled.")
elif peak < 1000:
    print("\n⚠ Audio is very quiet — mic may be muted or gain is very low.")
else:
    print("\n✓ Audio levels look good!")

out = "/tmp/debug_mic.wav"
with wave.open(out, "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(RATE)
    wf.writeframes(audio.tobytes())
print(f"\nSaved to {out} — play with: afplay {out}")
