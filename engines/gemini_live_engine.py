import asyncio
from typing import TYPE_CHECKING

import sounddevice as sd
from google import genai

from configs.config_manager import config as app_config
from engines.gemini_session import GeminiSession
from engines.wake_word import SAMPLE_RATE_IN, WakeWordDetector
from utils.logger import log

if TYPE_CHECKING:
    from registry import CommandRegistry


class GeminiLiveEngine:
    """Orchestrator: one always-on mic stream feeding both the wake word detector
    (24/7) and, while a conversation is live, the Gemini session.

    Wake word while idle  → start a session.
    Wake word while active → barge into the current response (keeps context).
    """

    def __init__(self, registry: "CommandRegistry") -> None:
        self.registry = registry
        cfg = app_config

        self._input_device       = cfg.infra.audio.input_device
        self._output_device      = cfg.infra.audio.output_device
        self._chunk_size         = cfg.infra.audio.chunk_size
        self._inactivity_timeout = cfg.infra.audio.inactivity_timeout

        if not cfg.infra.gemini.api_key:
            raise ValueError("Gemini API key is missing. Set GEMINI_API_KEY in your .env file.")
        self._client   = genai.Client(api_key=cfg.infra.gemini.api_key)
        self._model_id = cfg.infra.gemini.model

        self._loop: asyncio.AbstractEventLoop | None = None
        self._detector: WakeWordDetector | None = None
        self._session: GeminiSession | None = None
        self._session_task: asyncio.Task | None = None

        self._log_audio_devices()
        log.info(f"GeminiLiveEngine ready | model={self._model_id}")

    def _log_audio_devices(self) -> None:
        for kind, device in (("input", self._input_device), ("output", self._output_device)):
            label = device if device is not None else "default"
            try:
                info = sd.query_devices(device, kind)
                log.info(f"Audio {kind} → [{label}] {info['name']} ({int(info['default_samplerate'])} Hz)")
            except Exception as e:
                log.warning(f"Could not query {kind} device [{label}]: {e}")

    def _mic_callback(self, indata, frames, time_info, status) -> None:
        """PortAudio thread — fan each mic chunk to the detector (always) and to
        the Gemini session (only while one is active)."""
        if status:
            log.debug(f"Mic status: {status}")
        chunk = bytes(indata)
        self._detector.feed(chunk)
        session = self._session
        if session is not None and session.active:
            self._loop.call_soon_threadsafe(session.feed_mic, chunk)

    def _on_wake_detected(self) -> None:
        """Runs on the event loop. Start a session, or barge into the active one."""
        if self._session is not None:
            log.info("Barge-in — ducking then cutting playback, keeping the session")
            self._session.barge_in()
        else:
            self._session = GeminiSession(
                self._client, self._model_id, self.registry,
                self._inactivity_timeout, self._output_device,
            )
            self._session_task = asyncio.create_task(self._run_session(), name="session")

    async def _run_session(self) -> None:
        try:
            await self._session.run()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.error(f"Conversation error: {e}")
        finally:
            self._session = None
            self._session_task = None
            log.info(f"Listening for '{self._detector.name}'...")

    async def run(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._detector = WakeWordDetector.from_config(app_config, self._loop, self._on_wake_detected)
        self._detector.start()

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE_IN,
                channels=1,
                dtype="int16",
                blocksize=self._chunk_size,
                device=self._input_device,
                callback=self._mic_callback,
            ):
                log.info(f"Listening for '{self._detector.name}' 24/7...")
                await asyncio.Event().wait()   # run forever until cancelled
        except asyncio.CancelledError:
            log.info("Engine stopping...")
            if self._session_task and not self._session_task.done():
                self._session_task.cancel()
            self._detector.stop()
            raise
