import sounddevice as sd
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

    def speak(self, text: str):
        if not self.kokoro or not text:
            return
            
        try:
            log.debug(f"Synthesizing: {text[:30]}...")
            samples, sample_rate = self.kokoro.create(
                text, 
                voice=self.voice, 
                speed=1.0, 
                lang="en-us"
            )
            
            sd.play(samples, sample_rate)
            sd.wait()
            
        except Exception as e:
            log.error(f"TTS Synthesis Error: {e}")