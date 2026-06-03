<div align="center">

<img src="assets/naka.svg" alt="Naka logo" width="140" height="140">

# Naka

**A personal voice assistant for the Raspberry Pi, on-device wake word, Gemini Live brain.**

<p>
  <img alt="Status" src="https://img.shields.io/badge/status-early%20stage-orange?style=flat&labelColor=2b2b2b">
  <img alt="Stage" src="https://img.shields.io/badge/under-development-yellow?style=flat&labelColor=2b2b2b">
  <img alt="Platform" src="https://img.shields.io/badge/platform-Raspberry%20Pi-C51A4A?style=flat&logo=raspberrypi&logoColor=white&labelColor=2b2b2b">
</p>

<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white&labelColor=2b2b2b">
  <img alt="Gemini" src="https://img.shields.io/badge/Gemini%20Live-8E75B2?style=flat&logo=googlegemini&logoColor=white&labelColor=2b2b2b">
  <img alt="openWakeWord" src="https://img.shields.io/badge/openWakeWord-ONNX-005CED?style=flat&logo=onnx&logoColor=white&labelColor=2b2b2b">
  <img alt="uv" src="https://img.shields.io/badge/built%20with-uv-DE5FE9?style=flat&logo=uv&logoColor=white&labelColor=2b2b2b">
  <img alt="asyncio" src="https://img.shields.io/badge/asyncio-concurrent-2E8B57?style=flat&labelColor=2b2b2b">
</p>

</div>

> ⚠️ **Early stage / work in progress.** Naka is a personal project under active
> development. The architecture below is in place and working, but the surface is
> small, things move fast, and **many more commands are on the way**. Treat this
> as a foundation to build on, not a finished product.

Naka is a personal voice assistant designed to run on a **Raspberry Pi**. It pairs
**on-device wake-word detection** with **Gemini Live** (cloud) for speech-to-text,
reasoning, and text-to-speech inside a single WebSocket session so the Pi stays
near-idle and the heavy lifting happens server-side.

---

## How it works

```
Wake word (on-device, openWakeWord ONNX)
    ↓
Gemini Live WebSocket session
    ├── Audio IN  → mic stream, PCM 16-bit 16 kHz
    ├── STT + LLM → Gemini Flash Live
    ├── TTS       → Gemini native audio output, PCM 16-bit 24 kHz
    └── Function calling → CommandRegistry → BaseCommand.execute()
```

**Design choices:**

- **Everything cloud-side** (STT + LLM + TTS) to keep the Pi's load minimal.
- The **only on-device model is the wake word** (openWakeWord, ONNX).
- Audio playback is **decoupled** from the receive loop via an `asyncio.Queue`
  drained with a sentinel, so PortAudio never cuts speech off mid-sentence.
- Each session runs three concurrent async tasks (`send_audio`,
  `receive_responses`, `watchdog`) coordinated with `asyncio.Event` — no polling.

---

## Project layout

```
main.py                  Entry point — discovers commands, starts the engine
engines/
  gemini_live_engine.py  Orchestrates wake word + Gemini session + audio I/O
  gemini_session.py      The Gemini Live WebSocket session
  wake_word.py           On-device wake-word detection
commands/                Skills the assistant can call (auto-discovered)
  base_command.py        Abstract base: name, description, schema, execute()
  light_control.py       Turn lights on/off
  weather.py             Current weather (Open-Meteo, no API key)
  system_info.py         CPU + RAM via psutil
  media/                 Music playback (Spotify player + generic controls)
registry.py              Holds commands, builds Gemini function declarations
configs/                 Typed TOML config (Pydantic) + .env resolver
training/                Wake-word recording + training pipeline (see below)
models/wakeword/         The wake-word model loaded at startup
utils/                   Logger, HTTP client
```

---

## Commands (so far)

| Command | What it does |
|---|---|
| **Light control** | Turn lights on/off (kitchen, bedroom, living room) |
| **Weather** | Current conditions via Open-Meteo (no API key needed) |
| **System info** | Reports CPU and RAM usage |
| **Media** | Play / control music (Spotify, with a generic player layer) |

This list is intentionally short — **more commands are coming.** Adding one is
deliberately simple: subclass `BaseCommand`, implement `name` / `description` /
`parameters_schema` / `execute()`, drop it under `commands/`, and the registry
discovers it automatically.

---

## The wake word — not ready yet

This is the part still being figured out. The default openWakeWord models are
trained on **synthetic English** voices and recognize a non-English "naka" poorly.
The fix is a model trained **on your own voice**, and that pipeline lives in
[`training/`](training/).

A **first example model ships in the repo** at
[`models/wakeword/naka.onnx`](models/wakeword/naka.onnx) so Naka runs out of the
box — but consider it a **rough first pass**, not a finished, reliable detector.
Expect to retrain it on your own voice/mic/language for solid results.

👉 See [`training/README.md`](training/README.md) for the full record → train →
deploy → tune walkthrough.

---

## Status & roadmap (informal)

- ✅ Wake word → Gemini Live session → spoken response loop working
- ✅ Function-calling command system with auto-discovery
- ✅ A handful of commands (lights, weather, system info, media)
- 🚧 Wake-word model quality — example provided, needs proper training
- 🚧 Many more commands planned
- 🚧 APIs and config layout may still change

---

## Tech

`google-genai` · `openwakeword` · `sounddevice` · `numpy` · `pydantic` ·
`python-dotenv` · `psutil` — managed with **uv**.
