import speech_recognition as sr
from utils.logger import log
from configs.config_manager import config

class EarEngine:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        
        device_idx = config.infra['audio'].get('input_device', 0)
        self.rate = config.infra['audio'].get('sample_rate', 16000)
        
        try:
            self.mic = sr.Microphone(device_index=device_idx, sample_rate=self.rate)
            log.info(f"Mic started at {self.rate}Hz")
        except Exception as e:
            log.error(f"Failed to set sample rate: {e}")
    

    def listen(self):
        with self.mic as source:
            log.info("Listening... (Speak now)")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            lang = config.infra['audio'].get('language', 'en-US')
            
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                text = self.recognizer.recognize_google(audio, language=lang)
                return text
            except sr.UnknownValueError:
                log.error("Could not understand audio")
                return None
            except sr.RequestError as e:
                log.error(f"STT Error: {e}")
                return None