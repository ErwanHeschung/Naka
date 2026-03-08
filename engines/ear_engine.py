from utils.logger import log
from faster_whisper import WhisperModel
import sounddevice as sd
from configs.config_manager import config
from openwakeword.model import Model
import numpy as np

class EarEngine:
    def __init__(self):
        self.wake_word_name = config.ai['assistant'].get('wake_word', 'Naka')
        self.device_idx = config.infra['audio'].get('input_device', None)
        self.sample_rate = 16000
        
        self.whisper = WhisperModel("tiny.en", device="cpu", compute_type="int8")
        
        model_path = config.root / "models" / "wakeword" / f"{self.wake_word_name}.onnx"
        
        if model_path.exists():
            self.oww_model = Model(
                wakeword_model_paths=[str(model_path)]
            )
            log.info(f"Loaded custom wake word model: {model_path}")
        else:
            raise FileNotFoundError((f"Critical Error: {model_path} missing!"))
        
            
        log.info(f"Targeting Device ID: {self.device_idx}")
        log.info(f"EarEngine initialized. Listening for '{self.wake_word_name}'...")

    def wait_for_wake_word(self):
        chunk_size = 1280 
        with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype='float32', device=self.device_idx) as stream:
            while True:
                chunk, _ = stream.read(chunk_size)
                
                audio_scaled = (chunk.flatten() * 32768).astype(np.int16)
                
                prediction = self.oww_model.predict(audio_scaled)
                
                score = max(prediction.values()) if prediction else 0
                
                if score > 0.4:
                    volume = np.max(np.abs(audio_scaled))
                    print(f"Confidence: {score:.4f} | Vol: {int(volume):<5} \033[K", end="\r")
                    
                if score > 0.6:
                    print(f"\n{self.wake_word_name} detected!")
                    self.oww_model.reset()
                    return True

    def listen(self):
        """Step 1: Wait for name. Step 2: Record command."""
        if self.wait_for_wake_word():
            log.info("Recording command...")
            
            duration = 5
            recording = sd.rec(int(duration * self.sample_rate), 
                               samplerate=self.sample_rate, 
                               channels=1, dtype='float32',
                               device=self.device_idx)
            sd.wait()
            
            segments, _ = self.whisper.transcribe(recording.flatten(), beam_size=5)
            text = " ".join([s.text for s in segments]).strip()
            
            if text:
                log.info(f"Heard: {text}")
                return text
        return None