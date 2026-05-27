import asyncio
from typing import TYPE_CHECKING

import numpy as np
import sounddevice as sd
from google import genai
from google.genai import types
from openwakeword.model import Model as WakeWordModel

from configs.config_manager import config as app_config
from utils.logger import log

if TYPE_CHECKING:
    from registry import CommandRegistry

SAMPLE_RATE_IN  = 16_000
SAMPLE_RATE_OUT = 24_000


class GeminiLiveEngine:

    def __init__(self, registry: "CommandRegistry") -> None:
        self.registry = registry
        cfg = app_config

        self._wake_word_threshold = cfg.ai.assistant.wake_word_threshold
        self._input_device        = cfg.infra.audio.input_device
        self._output_device       = cfg.infra.audio.output_device
        self._chunk_size          = cfg.infra.audio.chunk_size
        self._inactivity_timeout  = cfg.infra.audio.inactivity_timeout

        self._setup_wake_word(cfg)
        self._setup_gemini(cfg)
        self._log_audio_devices()
        self._session_config = self._build_session_config()

        log.info(f"GeminiLiveEngine ready | model={self._model_id}")

    def _setup_wake_word(self, cfg) -> None:
        wake_word  = cfg.ai.assistant.wake_word
        model_path = cfg.root / "models" / "wakeword" / f"{wake_word}.onnx"

        if model_path.exists():
            self._oww_model = WakeWordModel(wakeword_model_paths=[str(model_path)])
            self._wake_word_name = wake_word
            log.info(f"Wake word: custom model '{wake_word}'")
        else:
            log.warning(
                f"Custom wake word model not found at '{model_path}'. "
                "Falling back to built-in OpenWakeWord models."
            )
            self._oww_model = WakeWordModel()
            available = list(self._oww_model.models.keys())
            self._wake_word_name = available[0] if available else "built-in"
            log.info(f"Built-in wake words available: {available}")

    def _setup_gemini(self, cfg) -> None:
        if not cfg.infra.gemini.api_key:
            raise ValueError(
                "Gemini API key is missing. Set GEMINI_API_KEY in your .env file."
            )
        self._client   = genai.Client(api_key=cfg.infra.gemini.api_key)
        self._model_id = cfg.infra.gemini.model

    def _log_audio_devices(self) -> None:
        for kind, device in (("input", self._input_device), ("output", self._output_device)):
            label = device if device is not None else "default"
            try:
                info = sd.query_devices(device, kind)
                log.info(f"Audio {kind} → [{label}] {info['name']} ({int(info['default_samplerate'])} Hz)")
            except Exception as e:
                log.warning(f"Could not query {kind} device [{label}]: {e}")

    def _build_session_config(self) -> types.LiveConnectConfig:
        ai = app_config.ai
        system_prompt = (
            f"You are {ai.assistant.name}. "
            f"{ai.personality.role} "
            f"Style: {ai.personality.style} "
            f"Instructions: {ai.personality.instructions}"
        )
        declarations = self.registry.get_function_declarations()
        tools = [types.Tool(function_declarations=declarations)] if declarations else []

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(parts=[types.Part(text=system_prompt)]),
            tools=tools,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=ai.assistant.gemini_voice
                    )
                )
            ),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )

    def _wait_for_wake_word(self) -> None:
        with sd.InputStream(
            samplerate=SAMPLE_RATE_IN,
            channels=1,
            dtype="float32",
            device=self._input_device,
        ) as stream:
            while True:
                chunk, _ = stream.read(self._chunk_size)
                audio_int16 = (chunk.flatten() * 32_768).astype(np.int16)
                prediction  = self._oww_model.predict(audio_int16)
                score       = max(prediction.values()) if prediction else 0.0
                if score > self._wake_word_threshold:
                    self._oww_model.reset()
                    log.info(f"Wake word '{self._wake_word_name}' detected (confidence={score:.2f})")
                    return

    async def _send_audio(self, session, stop_event: asyncio.Event) -> None:
        loop    = asyncio.get_running_loop()
        audio_q: asyncio.Queue[bytes] = asyncio.Queue()

        def _mic_callback(indata, frames, time_info, status) -> None:
            loop.call_soon_threadsafe(audio_q.put_nowait, bytes(indata))

        with sd.InputStream(
            samplerate=SAMPLE_RATE_IN,
            channels=1,
            dtype="int16",
            blocksize=self._chunk_size,
            device=self._input_device,
            callback=_mic_callback,
        ):
            while not stop_event.is_set():
                try:
                    chunk = await asyncio.wait_for(audio_q.get(), timeout=0.5)
                    await session.send_realtime_input(
                        audio=types.Blob(data=chunk, mime_type=f"audio/pcm;rate={SAMPLE_RATE_IN}")
                    )
                except asyncio.TimeoutError:
                    continue

    async def _handle_tool_call(self, session, tool_call) -> None:
        responses = []
        for fc in tool_call.function_calls:
            log.info(f"Function call → {fc.name}({dict(fc.args)})")
            result = self.registry.dispatch(fc.name, dict(fc.args))
            log.info(f"Function result → {result}")
            responses.append(
                types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result})
            )
        await session.send_tool_response(function_responses=responses)

    def _process_server_content(self, sc, turn_complete_event: asyncio.Event) -> None:
        if sc.input_transcription and sc.input_transcription.text:
            log.debug(f"You  : {sc.input_transcription.text}")
        if sc.output_transcription and sc.output_transcription.text:
            log.debug(f"Naka : {sc.output_transcription.text}")
        if sc.turn_complete:
            log.info("Turn complete — listening for next command")
            turn_complete_event.set()

    async def _play_audio(self, audio_q: asyncio.Queue) -> None:
        """Drains the audio queue into the output stream.

        Keeps playing until it receives the None sentinel, then lets
        sd.OutputStream.stop() flush the remaining PortAudio buffer before closing.
        """
        with sd.OutputStream(
            samplerate=SAMPLE_RATE_OUT,
            channels=1,
            dtype="int16",
            device=self._output_device,
        ) as out_stream:
            while True:
                chunk = await audio_q.get()
                if chunk is None:
                    break
                out_stream.write(np.frombuffer(chunk, dtype=np.int16))

    async def _receive_responses(
        self, session, turn_complete_event: asyncio.Event, audio_q: asyncio.Queue
    ) -> None:
        async for response in session.receive():
            if response.data:
                await audio_q.put(response.data)
            if response.tool_call:
                await self._handle_tool_call(session, response.tool_call)
            if response.server_content:
                self._process_server_content(response.server_content, turn_complete_event)

    async def _watchdog(self, stop_event: asyncio.Event, turn_complete_event: asyncio.Event) -> None:
        await turn_complete_event.wait()
        turn_complete_event.clear()

        while not stop_event.is_set():
            try:
                await asyncio.wait_for(turn_complete_event.wait(), timeout=self._inactivity_timeout)
                turn_complete_event.clear()
            except asyncio.TimeoutError:
                log.info(f"No activity for {self._inactivity_timeout}s — closing session")
                stop_event.set()
                return

    async def _handle_conversation(self) -> None:
        stop_event          = asyncio.Event()
        turn_complete_event = asyncio.Event()
        audio_q: asyncio.Queue[bytes | None] = asyncio.Queue()

        async with self._client.aio.live.connect(
            model=self._model_id, config=self._session_config
        ) as session:
            log.info("Gemini Live session opened")

            player_task = asyncio.create_task(self._play_audio(audio_q), name="play_audio")

            tasks = [
                asyncio.create_task(self._send_audio(session, stop_event),                           name="send_audio"),
                asyncio.create_task(self._receive_responses(session, turn_complete_event, audio_q),   name="receive_responses"),
                asyncio.create_task(self._watchdog(stop_event, turn_complete_event),                  name="watchdog"),
            ]

            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

            for task in done:
                if not task.cancelled() and task.exception():
                    log.error(f"Task error: {task.exception()}")

            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

            # Signal the player to stop, then wait for it to drain the PortAudio buffer
            await audio_q.put(None)
            await player_task

        log.info("Gemini Live session closed")

    async def run(self) -> None:
        log.info(f"Listening for '{self._wake_word_name}'...")
        loop = asyncio.get_running_loop()

        while True:
            await loop.run_in_executor(None, self._wait_for_wake_word)
            try:
                await self._handle_conversation()
            except Exception as e:
                log.error(f"Conversation error: {e}")
            log.info(f"Listening for '{self._wake_word_name}'...")
