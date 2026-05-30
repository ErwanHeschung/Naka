"""Quick mic check — prints the live input level for a given device.

Usage:
    uv run python training/mic_test.py          # uses configs/infra_config.toml
    uv run python training/mic_test.py 6        # force device index 6

Talk into the mic: the bar should react. Ctrl+C to stop.
"""
import sys
from pathlib import Path

import numpy as np
import sounddevice as sd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from configs.config_manager import config

SAMPLE_RATE_IN = 16_000

device = int(sys.argv[1]) if len(sys.argv) > 1 else config.infra.audio.input_device
info = sd.query_devices(device, "input")
print(f"Device [{device}] {info['name']} — {int(info['default_samplerate'])} Hz, "
      f"{info['max_input_channels']} ch")
print("Speak into the mic (Ctrl+C to stop)...\n")


def callback(indata, frames, time_info, status):
    if status:
        print(status)
    rms = np.sqrt(np.mean(indata.astype(np.float32) ** 2))
    level = int(rms / 500)          # rough scale for int16
    bar = "#" * min(level, 50)
    print(f"\rlevel {rms:6.0f} |{bar:<50}|", end="", flush=True)


with sd.InputStream(samplerate=SAMPLE_RATE_IN, channels=1, dtype="int16",
                    device=device, callback=callback):
    try:
        sd.sleep(10_000_000)
    except KeyboardInterrupt:
        print("\nStopped.")
