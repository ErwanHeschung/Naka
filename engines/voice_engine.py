import sounddevice as sd
import threading
import queue
from kokoro_onnx import Kokoro
from configs.config_manager import config
from utils.logger import log

class VoiceEngine:
    def __init__(self):
        model_path = config.root / "models" / "voice" / "kokoro-v1.0.int8.onnx"
        voices_path = config.root / "models" / "voice" / "voices-v1.0.bin"
        
        try:
            self.kokoro = Kokoro(str(model_path), str(voices_path))
            self.voice = config.ai['assistant'].get('voice', 'af_heart')
            log.info(f"Kokoro 82M initialized (Voice: {self.voice})")
        except Exception as e:
            log.error(f"Failed to load Kokoro: {e}")
            self.kokoro = None
            return

        self.speech_queue = queue.Queue()
        self.stop_event = threading.Event()
        
        self.worker_thread = threading.Thread(target=self._speech_worker, daemon=True)
        self.worker_thread.start()

    def speak(self, text: str):
        """Just adds text to the queue and returns immediately."""
        if text.strip():
            self.speech_queue.put(text)

    def _speech_worker(self):
        """Runs in the background, speaking everything in the queue."""
        while not self.stop_event.is_set():
            try:
                text = self.speech_queue.get(timeout=1)
                
                samples, sample_rate = self.kokoro.create(
                    text, voice=self.voice, speed=1.1, lang="en-us"
                )
                
                sd.play(samples, sample_rate)
                sd.wait() 
                self.speech_queue.task_done()
            except queue.Empty:
                continue