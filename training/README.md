# Training a personal wake word (voice-only)

Naka detects its name **on-device** with [openWakeWord](https://github.com/dscripka/openWakeWord).
The default model is trained on **synthetic English** voices, so it recognizes a
non-English pronunciation poorly (a French "naka" won't trigger it). The clean fix
is a model trained **on your own voice**, in your language, with your mic.

> **Key idea:** you don't need thousands of samples. ~150 **varied** recordings
> plus augmentation (room reverb + background noise, done automatically) are
> enough for a robust personal wake word. What matters is the **diversity** of the
> takes, not their raw count.

---

## Overview

```
1. record_samples.py   → record YOUR voice (same mic as Naka)
2. zip                 → samples.zip
3. naka_voice_training.ipynb (Colab, T4 GPU) → train, export <wake_word>.onnx
4. drop the .onnx      → models/wakeword/<wake_word>.onnx
5. wake_test.py        → tune the threshold
```

Files involved:

| File | Role |
|---|---|
| [`training/record_samples.py`](record_samples.py) | Record your positive samples |
| [`training/naka_voice_training.ipynb`](naka_voice_training.ipynb) | Voice-only training notebook (Colab) |
| [`training/wake_test.py`](wake_test.py) | Live score monitor for tuning the threshold |
| [`training/mic_test.py`](mic_test.py) | Live mic level (device sanity check) |
| [`training/mic_record.py`](mic_record.py) | Record a WAV to spot dropouts/cuts |
| `models/wakeword/<wake_word>.onnx` | The model Naka loads at startup |
| [`configs/ai_config.toml`](../configs/ai_config.toml) | `wake_word` + `wake_word_threshold` |

---

## Step 1 — Record your samples

Plug in the mic you'll actually use with Naka (e.g. the headset), then:

```bash
uv run python training/record_samples.py 150
```

- Writes to `training/training_data/<wake_word>/` (`wake_word` comes from `ai_config.toml`).
- Continues the **numbering** where it left off: rerun it to add more.
- Each clip shows **how** to say it — follow it. Variety drives robustness:
  - volume: normal / louder / whispered
  - pace: normal / fast / slow and articulated
  - distance & orientation: close / far / head turned
  - a few takes **with background sound** (music, fan)
- Clips that are too quiet or clipping are **rejected and retried** automatically.
- `Enter` records, `q` quits (keeps everything already recorded).

**How many?** 150 is a good starting point for a single speaker. 250–300 for extra
robustness margin. Force a device index: `... 150 1`.

Sanity-check the mic (optional):

```bash
uv run python training/mic_test.py       # the level should react when you speak
```

## Step 2 — Zip

Compress the `training/training_data/<wake_word>/` folder into `samples.zip`
(the notebook accepts any tree of `.wav` files inside).

## Step 3 — Train (Google Colab)

1. Open [`naka_voice_training.ipynb`](naka_voice_training.ipynb) in Colab.
2. Runtime → **T4 GPU**.
3. Cell 1: set `target_word` **identical** to `wake_word` in `ai_config.toml`.
4. Run the cells in order:
   - **1** setup, **2** data (RIR + noise + features, ~15 min),
   - **3a** generates the adversarial negatives + folder structure (synthetic English positives are created here…),
   - **3b** …then **discarded**: only **your** recordings are injected (upload `samples.zip`),
   - **3c** augmentation → training → export → download of `<wake_word>.onnx`.

Knobs to tweak if needed (cell 3b / 3a):

| Parameter | Default | When to raise it |
|---|---|---|
| `DUPLICATE` | 3 | Few samples → 5–8 (more augmented variants) |
| `number_of_examples` | 200 | No need to raise: these English positives are discarded |
| `false_activation_penalty` | 1500 | Too many false triggers → raise (2000–3000) |
| `number_of_training_steps` | 10000 | Underfitting → raise |

## Step 4 — Deploy

Drop the downloaded `.onnx` into:

```
models/wakeword/<wake_word>.onnx
```

(`models/` is gitignored — that's expected). Naka loads it automatically at
startup; otherwise it falls back to openWakeWord's built-in models with a warning.

## Step 5 — Tune the threshold

```bash
uv run python training/wake_test.py
```

Say the wake word: the `peak` should cross the threshold. Then **talk normally for
~5 min without saying it**: the score must never trigger. Adjust in
[`configs/ai_config.toml`](../configs/ai_config.toml):

```toml
wake_word_threshold = 0.5   # higher = fewer false positives, less sensitive
```

Rule of thumb: set the threshold **a bit below** your `peak` when you say the word,
but **above** the noise you see when you don't.

---

## Adapting it to another word / language

The pipeline is generic — nothing is hardcoded to "naka" or to French:

1. Change `wake_word` in `configs/ai_config.toml`.
2. `uv run python training/record_samples.py 150` in **your** language/accent/mic.
3. Set the notebook's `target_word` equal to that `wake_word`.
4. Train, drop `models/wakeword/<wake_word>.onnx`, tune the threshold.

Since the positives are **only your voice**, the model matches your pronunciation
and has no dependency on English. Everyone trains their own.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Never triggers in your language | Model dominated by synthetic English | Retrain **voice-only** (this notebook) |
| `rms` moves but `score` stays ~0 in `training/wake_test.py` | Model doesn't recognize your voice/mic | More varied samples + retrain |
| `rms` stays ~0 even while speaking | Wrong input device | Uncomment `input_device` in `infra_config.toml` (`uv run python -m sounddevice` for the index) |
| Triggers on its own | Threshold too low / penalty too weak | Raise `wake_word_threshold` and/or `false_activation_penalty` |
| "Custom wake word model not found" at startup | `.onnx` missing or misnamed | Check `models/wakeword/<wake_word>.onnx` (name == `wake_word`) |
| Colab: `ValueError: mmap length is greater than file size` at train time | A feature `.npy` download was truncated (the exists-check kept the bad file) | Re-run the data cell — it now verifies each `.npy` and re-downloads truncated ones |
| Colab: `onnx2tf` / `InterpreterWrapper already registered` | TF/ai-edge-litert version clash; TFLite export only | Harmless — Naka uses the `.onnx`. Cell 3c now skips TFLite automatically |
