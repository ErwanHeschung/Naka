"""Record wake-word samples for training a personal openWakeWord model.

Records short clips of YOU saying the wake word, in your own language/accent, on
the SAME mic you use with Naka (e.g. the headset). These clips become the
*positive* examples for a voice-only model — see training/README.md.

Usage:
    uv run python training/record_samples.py            # 100 clips, configured wake word + default mic
    uv run python training/record_samples.py 150        # 150 clips
    uv run python training/record_samples.py 150 1      # 150 clips, force input device index 1

Per clip a prompt tells you HOW to say it. Varying tone / distance / volume /
speed is what makes the model robust — follow the prompts, don't say it the same
way 150 times. Clips that are too quiet or clipping are auto-rejected and retried.

Controls:
    Enter   record this clip
    q       quit early (keeps everything recorded so far)
"""
import sys
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from configs.config_manager import config

SAMPLE_RATE = 16_000     # Hz — must match what Naka feeds the detector
DURATION    = 2.0        # seconds captured per clip (speak right after Enter)
MIN_RMS     = 150        # below this the clip is too quiet → auto-retry
CLIP_PEAK   = 32000      # above this the clip is saturating → auto-retry

PROMPTS = [
    "normal voice, normal distance",
    "a bit louder",
    "a bit softer",
    "faster",
    "slower, articulating the syllables",
    "moving a bit away from the mic",
    "with your head turned to the side",
    "normal voice",
    "as if calling someone across the room",
    "quietly, almost whispered",
]


def record_clip(device) -> np.ndarray:
    audio = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                   channels=1, dtype="int16", device=device)
    sd.wait()
    return audio.reshape(-1)


def write_wav(path: Path, audio: np.ndarray) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)            # int16
        w.setframerate(SAMPLE_RATE)
        w.writeframes(audio.tobytes())


def main() -> None:
    n      = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    device = int(sys.argv[2]) if len(sys.argv) > 2 else config.infra.audio.input_device
    wake   = config.ai.assistant.wake_word

    out_dir = config.root / "training" / "training_data" / wake
    out_dir.mkdir(parents=True, exist_ok=True)

    existing = sorted(out_dir.glob(f"{wake}_*.wav"))
    nums  = [int(p.stem.rsplit("_", 1)[-1]) for p in existing if p.stem.rsplit("_", 1)[-1].isdigit()]
    start = (max(nums) + 1) if nums else 0

    info  = sd.query_devices(device, "input")
    label = device if device is not None else "default"
    print(f"Device [{label}] {info['name']} @ {SAMPLE_RATE} Hz")
    print(f"Wake word: '{wake}'  →  {out_dir}")
    print(f"{len(existing)} existing clip(s); recording {n} more, numbered from #{start:03d}.")
    print("Say the wake word ONCE per clip, right after pressing Enter. Vary it as prompted.\n")

    saved = 0
    while saved < n:
        idx    = start + saved
        prompt = PROMPTS[saved % len(PROMPTS)]
        cmd = input(f"[{saved + 1}/{n}] #{idx:03d}  say \"{wake}\" ({prompt}) — Enter=rec, q=quit: ")
        if cmd.strip().lower() == "q":
            break

        audio = record_clip(device)
        rms   = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))
        peak  = int(np.abs(audio).max())

        if rms < MIN_RMS:
            print(f"    rms {rms:5.0f} — too quiet, retrying.\n")
            continue
        if peak >= CLIP_PEAK:
            print(f"    peak {peak} — clipping, speak softer / move back, retrying.\n")
            continue

        write_wav(out_dir / f"{wake}_{idx:03d}.wav", audio)
        saved += 1
        print(f"    rms {rms:5.0f}  peak {peak}  ✓ saved\n")

    print(f"Done. {saved} new clip(s) saved → {out_dir}")
    print(f"Total clips now: {len(list(out_dir.glob(f'{wake}_*.wav')))}")
    print("Next: zip that folder and follow training/README.md")


if __name__ == "__main__":
    main()
