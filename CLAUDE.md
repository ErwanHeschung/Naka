# Naka — Claude Context

## What this is
Naka is a personal voice assistant designed to run on a Raspberry Pi.
It combines on-device wake-word detection with Gemini Live (cloud) for STT + LLM + TTS in a single WebSocket session.

## Architecture

```
Wake word (on-device, OpenWakeWord)
    ↓
Gemini Live WebSocket session
    ├── Audio IN  → mic stream, PCM 16-bit 16 kHz
    ├── STT + LLM → Gemini 2.5 Flash Live
    ├── TTS       → Gemini native audio output, PCM 16-bit 24 kHz
    └── Function calling → CommandRegistry → BaseCommand.execute()
```

**Key design decisions:**
- Everything cloud-side (STT + LLM + TTS) to keep the Pi load near zero
- Wake word is the only on-device model — OpenWakeWord ONNX (~80 MB)
- Audio playback is decoupled from the receive loop via `asyncio.Queue` + sentinel `None` to prevent PortAudio cutting audio mid-sentence on session teardown
- Three concurrent async tasks per session: `send_audio`, `receive_responses`, `watchdog`
- Watchdog uses `asyncio.wait_for(event.wait(), timeout=...)` — no polling

## File map

```
main.py                          Entry point — registers commands, starts engine
engines/
  gemini_live_engine.py          The whole brain: wake word + Gemini session + audio I/O
commands/
  base_command.py                Abstract: name, description, parameters_schema, execute()
  light_control.py               Turn lights on/off (kitchen, bedroom, living_room)
  weather.py                     Current weather via Open-Meteo (no API key needed)
  system_info.py                 CPU + RAM via psutil
registry.py                      Holds commands, generates Gemini function declarations
configs/
  config_manager.py              Pydantic models + TOML loader + .env resolver
  ai_config.toml                 Assistant personality, wake word, voice, threshold
  infra_config.toml              Gemini model, audio devices, chunk size, timeout
utils/
  logger.py                      Coloured console logger (`log` singleton)
```

## Config — typed access (Pydantic)

```python
config.ai.assistant.name              # "Naka"
config.ai.assistant.wake_word         # "naka"
config.ai.assistant.gemini_voice      # "Puck"
config.ai.assistant.wake_word_threshold  # 0.6
config.ai.personality.role
config.ai.personality.style
config.ai.personality.instructions

config.infra.gemini.model             # "gemini-3.1-flash-live-preview"
config.infra.gemini.api_key           # from GEMINI_API_KEY in .env
config.infra.audio.input_device       # int | None  (None = OS default)
config.infra.audio.output_device      # int | None
config.infra.audio.chunk_size         # 1280 samples
config.infra.audio.inactivity_timeout # 15.0 seconds
```

**Never use dict-style access** (`config.ai["assistant"]`). Always use attribute access.

## Adding a new command

1. Create `commands/my_command.py` inheriting `BaseCommand`
2. Implement `name`, `description`, `parameters_schema` (JSON Schema), `execute()`
3. Register in `main.py`: `reg.register(MyCommand())`

`parameters_schema` must be valid JSON Schema. Commands with no parameters use `{"type": "object", "properties": {}}`.

## Audio constants (Gemini API requirements — not configurable)

```python
SAMPLE_RATE_IN  = 16_000   # Hz — mic input
SAMPLE_RATE_OUT = 24_000   # Hz — speaker output
```

## API notes

- Gemini Live model: `gemini-3.1-flash-live-preview`
- SDK: `google-genai` (not `google-generativeai`)
- No `http_options` override needed — default `v1beta` endpoint works
- Transcriptions enabled: `input_audio_transcription` + `output_audio_transcription` in session config
- Function declarations passed as `types.Tool(function_declarations=[...])`

## Dependencies (pyproject.toml)

```
google-genai        Gemini Live API
openwakeword        Wake word detection (on-device)
sounddevice         Audio I/O (PortAudio wrapper)
numpy               Audio array manipulation
pydantic            Config validation
python-dotenv       .env loader
psutil              System metrics (SystemInfo command)
```

## What NOT to do

- Don't hardcode values in engine code — they belong in the TOML configs
- Don't use `asyncio.sleep()` polling in tasks — use `asyncio.Event` with `wait_for`
- Don't cancel `_play_audio` directly — always send `None` sentinel to drain the buffer first
- Don't install models in the repo — `models/` is gitignored
