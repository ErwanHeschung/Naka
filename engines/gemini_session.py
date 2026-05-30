import asyncio
from typing import TYPE_CHECKING

import numpy as np
import sounddevice as sd
from google import genai
from google.genai import types

from configs.config_manager import config as app_config
from utils.logger import log

if TYPE_CHECKING:
    from registry import CommandRegistry

SAMPLE_RATE_IN  = 16_000
SAMPLE_RATE_OUT = 24_000

DUCK_GAIN   = 0.2    # volume multiplier applied to the residual on barge-in
DUCK_CHUNKS = 2      # chunks played ducked as a fade before cutting


class GeminiSession:
    """One Gemini Live conversation: send mic audio, play responses, run tools.

    A session opens on wake-word detection and stays open across multiple turns
    until *inactivity_timeout* of silence. The owning engine feeds mic chunks via
    :meth:`feed_mic` and interrupts the current response via :meth:`barge_in`.
    """

    def __init__(
        self,
        client: genai.Client,
        model_id: str,
        registry: "CommandRegistry",
        inactivity_timeout: float,
        output_device: int | None,
    ) -> None:
        self._client             = client
        self._model_id           = model_id
        self.registry            = registry
        self._inactivity_timeout = inactivity_timeout
        self._output_device      = output_device

        self.active        = False
        self._gemini_q: asyncio.Queue[bytes]        = asyncio.Queue()
        self._audio_q: asyncio.Queue[bytes | None]  = asyncio.Queue()
        self._muted          = asyncio.Event()
        self._activity_event = asyncio.Event()
        self._duck_remaining = 0

    # ------------------------------------------------------------------ #
    # Called from the engine                                             #
    # ------------------------------------------------------------------ #

    def feed_mic(self, chunk: bytes) -> None:
        """Forward a mic chunk into the session. Runs on the event loop."""
        self._gemini_q.put_nowait(chunk)

    def barge_in(self) -> None:
        """Interrupt the current spoken response without closing the session.

        If Naka is talking, duck the volume for a short fade then drop the rest of
        the response (handled by the player). The always-on mic then flows back to
        Gemini in the same session, so the conversation context is kept.
        """
        if self._muted.is_set():
            self._duck_remaining = DUCK_CHUNKS   # player fades out then cuts
        else:
            self._drain_audio_queue()            # not speaking — just clear backlog
        self._activity_event.set()               # reset the inactivity window

    # ------------------------------------------------------------------ #
    # Config                                                             #
    # ------------------------------------------------------------------ #

    def _build_config(self, tags: list[str] | None = None) -> types.LiveConnectConfig:
        ai = app_config.ai
        system_prompt = (
            f"You are {ai.assistant.name}.\n\n"
            f"{ai.personality.role}\n\n"
            f"Style: {ai.personality.style}\n\n"
            f"Instructions:\n{ai.personality.instructions}"
        )
        declarations = self.registry.get_function_declarations(tags=tags)
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

    def _drain_audio_queue(self) -> None:
        try:
            while True:
                self._audio_q.get_nowait()
        except asyncio.QueueEmpty:
            pass

    # ------------------------------------------------------------------ #
    # Tasks                                                              #
    # ------------------------------------------------------------------ #

    async def _send_audio(self, session, stop_event: asyncio.Event) -> None:
        """Forward mic chunks to Gemini, skipping playback to avoid echo."""
        while not stop_event.is_set():
            try:
                chunk = await asyncio.wait_for(self._gemini_q.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            if self._muted.is_set():
                continue
            await session.send_realtime_input(
                audio=types.Blob(data=chunk, mime_type=f"audio/pcm;rate={SAMPLE_RATE_IN}")
            )

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

    def _process_server_content(self, sc) -> None:
        if getattr(sc, "interrupted", False):
            self._drain_audio_queue()   # Gemini's VAD heard the user — drop stale audio
        if sc.input_transcription and sc.input_transcription.text:
            log.debug(f"You  : {sc.input_transcription.text}")
            self._activity_event.set()
        if sc.output_transcription and sc.output_transcription.text:
            log.debug(f"Naka : {sc.output_transcription.text}")
            self._activity_event.set()
        if sc.turn_complete:
            log.info("Turn complete — listening for next command")
            self._activity_event.set()

    async def _play_audio(self) -> None:
        """Drain the audio queue to the speaker.

        Resets the inactivity timer on every chunk played, so the silence window
        is measured from when playback actually *ends* (Gemini streams its audio
        in a burst well before it finishes playing). On barge-in the next few
        chunks fade out then the rest of the response is dropped. The None
        sentinel drains the PortAudio buffer cleanly on teardown.
        """
        loop = asyncio.get_running_loop()
        with sd.OutputStream(
            samplerate=SAMPLE_RATE_OUT,
            channels=1,
            dtype="int16",
            device=self._output_device,
            latency="low",
        ) as out_stream:
            while True:
                chunk = await self._audio_q.get()
                if chunk is None:
                    break
                samples = np.frombuffer(chunk, dtype=np.int16)
                self._activity_event.set()

                if self._duck_remaining > 0:
                    self._duck_remaining -= 1
                    ducked = (samples * DUCK_GAIN).astype(np.int16)
                    await loop.run_in_executor(None, out_stream.write, ducked)
                    if self._duck_remaining == 0:
                        self._drain_audio_queue()   # fade done → drop the rest of the turn
                        self._muted.clear()
                    continue

                self._muted.set()
                await loop.run_in_executor(None, out_stream.write, samples)
                if self._audio_q.empty():
                    self._muted.clear()
                    self._duck_remaining = 0        # never carry a barge-in into the next turn
        self._muted.clear()

    async def _receive_responses(self, session, stop_event: asyncio.Event) -> None:
        """Receive across turns. session.receive() ends at each turn_complete, so
        re-enter it until the watchdog stops the session or the connection drops.
        """
        while not stop_event.is_set():
            got_any = False
            async for response in session.receive():
                got_any = True
                if response.data:
                    await self._audio_q.put(response.data)
                    self._activity_event.set()
                if response.tool_call:
                    await self._handle_tool_call(session, response.tool_call)
                if response.server_content:
                    self._process_server_content(response.server_content)
            if not got_any:
                break   # connection closed

    async def _watchdog(self, stop_event: asyncio.Event) -> None:
        """Close the session after *inactivity_timeout* of true silence.

        Any activity — user speech, Naka audio, turn completion, barge-in — resets
        the timer. Applies from session start, so a stray wake word with no
        follow-up speech still tears the session down.
        """
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(self._activity_event.wait(), timeout=self._inactivity_timeout)
                self._activity_event.clear()
            except asyncio.TimeoutError:
                log.info(f"No activity for {self._inactivity_timeout}s — closing session")
                stop_event.set()
                return

    async def run(self) -> None:
        stop_event = asyncio.Event()
        try:
            async with self._client.aio.live.connect(
                model=self._model_id, config=self._build_config()
            ) as session:
                log.info("Gemini Live session opened")
                self.active = True

                player_task = asyncio.create_task(self._play_audio(), name="play_audio")
                tasks = [
                    asyncio.create_task(self._send_audio(session, stop_event),       name="send_audio"),
                    asyncio.create_task(self._receive_responses(session, stop_event), name="receive_responses"),
                    asyncio.create_task(self._watchdog(stop_event),                   name="watchdog"),
                ]

                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

                for task in done:
                    if not task.cancelled() and task.exception():
                        log.error(f"Task error: {task.exception()}")

                stop_event.set()
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)

                # Stop the player, then let it drain the PortAudio buffer
                await self._audio_q.put(None)
                await player_task

            log.info("Gemini Live session closed")
        finally:
            self.active = False
