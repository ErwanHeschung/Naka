"""Live wake-word score monitor — same input path as Naka.

Opens the default input device (exactly like the engine: device=None) and runs
the configured wake-word model, printing the live score so you can see whether
saying the wake word actually crosses the threshold on a given mic.

Usage:
    uv run python training/wake_test.py          # default device (what Naka uses)
    uv run python training/wake_test.py 1        # force device index 1

Say the wake word into the mic. Watch the bar:
  - score climbs past the threshold when you say it  → wake word is fine
  - score never moves off ~0.00 even when you speak  → mic data isn't reaching
    the detector (device binding), not a model problem
Ctrl+C to stop.
"""
import sys
from pathlib import Path

import numpy as np
import sounddevice as sd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from configs.config_manager import config
from openwakeword.model import Model as WakeWordModel

SAMPLE_RATE_IN = 16_000

device = int(sys.argv[1]) if len(sys.argv) > 1 else config.infra.audio.input_device
chunk  = config.infra.audio.chunk_size
thr    = config.ai.assistant.wake_word_threshold

wake_word  = config.ai.assistant.wake_word
model_path = config.root / "models" / "wakeword" / f"{wake_word}.onnx"
if model_path.exists():
    model = WakeWordModel(wakeword_model_paths=[str(model_path)])
    print(f"Model: custom '{wake_word}' ({model_path.name})")
else:
    model = WakeWordModel()
    print(f"Model: built-in (no custom model at {model_path})")

label = device if device is not None else "default"
info  = sd.query_devices(device, "input")
print(f"Device [{label}] {info['name']} — threshold={thr}, chunk={chunk}")
print(f"Say '{wake_word}' into the mic (Ctrl+C to stop)...\n")

peak = 0.0


def callback(indata, frames, time_info, status):
    global peak
    if status:
        print(f"\n  ⚠ {status}")
    audio = np.frombuffer(bytes(indata), dtype=np.int16)
    rms   = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))
    pred  = model.predict(audio)
    score = max(pred.values()) if pred else 0.0
    peak  = max(peak, score)
    hit   = "  <== WAKE" if score > thr else ""
    bar   = "#" * int(score * 40)
    print(f"\rrms {rms:6.0f}  score {score:0.3f} peak {peak:0.3f} |{bar:<40}|{hit}",
          end="", flush=True)


with sd.InputStream(samplerate=SAMPLE_RATE_IN, channels=1, dtype="int16",
                    blocksize=chunk, device=device, callback=callback):
    try:
        sd.sleep(10_000_000)
    except KeyboardInterrupt:
        print(f"\nStopped. Highest score seen: {peak:0.3f} (threshold {thr}).")
