import asyncio
import queue
import threading
from collections.abc import Callable

import numpy as np
from openwakeword.model import Model as WakeWordModel

from utils.logger import log

SAMPLE_RATE_IN = 16_000


class WakeWordDetector:
    """Always-on wake word detection running in a dedicated thread.

    Audio is pushed in via :meth:`feed` (from the mic callback thread); OWW
    inference runs in its own thread so it never blocks the event loop (ONNX
    releases the GIL). On detection it hops back to the loop and invokes
    *on_detected*.
    """

    def __init__(
        self,
        model: WakeWordModel,
        name: str,
        threshold: float,
        loop: asyncio.AbstractEventLoop,
        on_detected: Callable[[], None],
    ) -> None:
        self._model       = model
        self.name         = name
        self._threshold   = threshold
        self._loop        = loop
        self._on_detected = on_detected

        self._queue: queue.Queue[bytes] = queue.Queue()
        self._shutdown = threading.Event()
        self._thread: threading.Thread | None = None

    @classmethod
    def from_config(
        cls,
        cfg,
        loop: asyncio.AbstractEventLoop,
        on_detected: Callable[[], None],
    ) -> "WakeWordDetector":
        wake_word  = cfg.ai.assistant.wake_word
        model_path = cfg.root / "models" / "wakeword" / f"{wake_word}.onnx"

        if model_path.exists():
            model = WakeWordModel(wakeword_model_paths=[str(model_path)])
            name  = wake_word
            log.info(f"Wake word: custom model '{wake_word}'")
        else:
            log.warning(
                f"Custom wake word model not found at '{model_path}'. "
                "Falling back to built-in OpenWakeWord models."
            )
            model     = WakeWordModel()
            available = list(model.models.keys())
            name      = available[0] if available else "built-in"
            log.info(f"Built-in wake words available: {available}")

        return cls(model, name, cfg.ai.assistant.wake_word_threshold, loop, on_detected)

    def feed(self, chunk: bytes) -> None:
        """Queue a mic chunk for detection. Safe to call from any thread."""
        self._queue.put_nowait(chunk)

    def start(self) -> None:
        self._shutdown.clear()
        self._thread = threading.Thread(target=self._worker, name="wake_word", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._shutdown.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _drain(self) -> None:
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass

    def _worker(self) -> None:
        log.info(f"Wake word thread up — listening for '{self.name}' 24/7")
        while not self._shutdown.is_set():
            try:
                chunk = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            audio_int16 = np.frombuffer(chunk, dtype=np.int16)
            prediction  = self._model.predict(audio_int16)
            score       = max(prediction.values()) if prediction else 0.0
            if score > 0.1:
                log.debug(f"wake: score={score:.3f} (thr={self._threshold})")
            if score > self._threshold:
                self._model.reset()   # ~400ms refractory (first 5 frames → 0)
                self._drain()          # drop backlog so we don't re-trigger
                log.info(f"Wake word '{self.name}' detected (confidence={score:.2f})")
                self._loop.call_soon_threadsafe(self._on_detected)
