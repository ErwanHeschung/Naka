"""Record from the mic to a WAV file to check for dropouts / cuts.

Usage:
    uv run python training/mic_record.py             # 10s, device from config
    uv run python training/mic_record.py 20          # 20 seconds
    uv run python training/mic_record.py 20 6        # 20 seconds, device index 6

Output: training/recording.wav  (PCM 16-bit, 16 kHz — same format Gemini gets).
Any PortAudio under/overflows are printed inline: those are real dropouts.
"""
import sys
import wave
from pathlib import Path

import sounddevice as sd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from configs.config_manager import config

SAMPLE_RATE_IN = 16_000

duration = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
device   = int(sys.argv[2]) if len(sys.argv) > 2 else config.infra.audio.input_device
out_path = Path(__file__).resolve().parent / "recording.wav"

info = sd.query_devices(device, "input")
print(f"Device [{device}] {info['name']} — recording {duration:.0f}s at {SAMPLE_RATE_IN} Hz")
print("Speak now... (drops will be flagged below)\n")

glitches = 0


def callback(indata, frames, time_info, status):
    global glitches
    if status:
        glitches += 1
        print(f"  ⚠ {status}")
    wav.writeframes(bytes(indata))


with wave.open(str(out_path), "wb") as wav:
    wav.setnchannels(1)
    wav.setsampwidth(2)            # int16
    wav.setframerate(SAMPLE_RATE_IN)
    with sd.InputStream(samplerate=SAMPLE_RATE_IN, channels=1, dtype="int16",
                        blocksize=config.infra.audio.chunk_size,
                        device=device, callback=callback):
        sd.sleep(int(duration * 1000))

print(f"\nDone. {glitches} glitch(es) reported by PortAudio.")
print(f"Saved → {out_path}")
print("Play it back to hear if your speech is continuous.")
